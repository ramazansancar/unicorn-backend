from collections import OrderedDict

import pytz
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as ModelValidationError
from django.db.models import ManyToManyField
from django.http import Http404
from guardian.shortcuts import get_perms
from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.response import Response
from rest_framework.serializers import (
    Field,
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)
from rest_framework.viewsets import ModelViewSet as _ModelViewSet
from rest_framework.viewsets import ViewSet

from .utils import dynamic_import

WRITE_OPERATIONS = ["create", "update", "partial_update", "delete"]


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable, please try again later."


def get_serializer_for_model(model, prefix=""):
    """
    Dynamically resolve and return the appropriate serializer for a model.
    """
    app_name, model_name = model._meta.label.split(".")
    serializer_name = "{}.api.serializers.{}{}Serializer".format(app_name, prefix, model_name)
    try:
        return dynamic_import(serializer_name)
    except AttributeError:
        return None


#
# Authentication
#


class IsAuthenticatedOrLoginNotRequired(BasePermission):
    """
    Returns True if the user is authenticated or LOGIN_REQUIRED is False.
    """

    def has_permission(self, request, view):
        if not settings.LOGIN_REQUIRED:
            return True
        return request.user.is_authenticated()


#
# Fields
#


class ChoiceField(Field):
    """
    Represent a ChoiceField as {'value': <DB value>, 'label': <string>}.
    """

    def __init__(self, choices, **kwargs):
        self._choices = dict()
        for k, v in choices:
            # Unpack grouped choices
            if type(v) in [list, tuple]:
                for k2, v2 in v:
                    self._choices[k2] = v2
            else:
                self._choices[k] = v
        super(ChoiceField, self).__init__(**kwargs)

    def to_representation(self, obj):
        return {"value": obj, "label": self._choices[obj]}

    def to_internal_value(self, data):
        # Hotwiring boolean values
        if hasattr(data, "lower"):
            if data.lower() == "true":
                return True
            if data.lower() == "false":
                return False
        return data


class ContentTypeField(Field):
    """
    Represent a ContentType as '<app_label>.<model>'
    """

    def to_representation(self, obj):
        return "{}.{}".format(obj.app_label, obj.model)

    def to_internal_value(self, data):
        app_label, model = data.split(".")
        try:
            return ContentType.objects.get_by_natural_key(app_label=app_label, model=model)
        except ContentType.DoesNotExist:
            raise ValidationError("Invalid content type")


class TimeZoneField(Field):
    """
    Represent a pytz time zone.
    """

    def to_representation(self, obj):
        return obj.zone if obj else None

    def to_internal_value(self, data):
        if not data:
            return ""
        try:
            return pytz.timezone(str(data))
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValidationError('Invalid time zone "{}"'.format(data))


class SerializedPKRelatedField(PrimaryKeyRelatedField):
    """
    Extends PrimaryKeyRelatedField to return a serialized object on read. This is useful for representing related
    objects in a ManyToManyField while still allowing a set of primary keys to be written.
    """

    def __init__(self, serializer, **kwargs):
        self.serializer = serializer
        self.pk_field = kwargs.pop("pk_field", None)
        super(SerializedPKRelatedField, self).__init__(**kwargs)

    def to_representation(self, value):
        return self.serializer(value, context={"request": self.context["request"]}).data


#
# Serializers
#

# TODO: We should probably take a fresh look at exactly what we're doing with this. There might be a more elegant
# way to enforce model validation on the serializer.
class ValidatedModelSerializer(ModelSerializer):
    """
    Extends the built-in ModelSerializer to enforce calling clean() on the associated model during validation.
    """

    obj_type = SerializerMethodField()
    permissions = SerializerMethodField()

    def validate(self, data):
        attrs = data.copy()

        # Skip ManyToManyFields
        for field in self.Meta.model._meta.get_fields():
            if isinstance(field, ManyToManyField):
                attrs.pop(field.name, None)

        # Run clean() on an instance of the model
        if self.instance is None:
            instance = self.Meta.model(**attrs)
        else:
            instance = self.instance
            for k, v in attrs.items():
                setattr(instance, k, v)

        try:
            instance.clean()
        except ModelValidationError as e:
            raise ValidationError(e.args[0])

        return data

    def get_obj_type(self, obj) -> str:
        return "full"

    def get_permissions(self, obj) -> list:
        return [f"{obj._meta.app_label}.{p}" for p in list(get_perms(self.context["request"].user, obj))]


class WritableNestedSerializer(ModelSerializer):
    """
    Returns a nested representation of an object on read, but accepts only a primary key on write.
    """

    obj_type = SerializerMethodField()

    def to_internal_value(self, data):
        if data is None:
            return None
        try:
            return self.Meta.model.objects.get(pk=int(data))
        except (TypeError, ValueError):
            raise ValidationError("Primary key must be an integer")
        except ObjectDoesNotExist:
            raise ValidationError("Invalid ID")

    def get_obj_type(self, obj) -> str:
        return "nested"


#
# Viewsets
#


class ModelViewSet(_ModelViewSet):
    """
    Accept either a single object or a list of objects to create.
    """

    def get_serializer(self, *args, **kwargs):

        # If a list of objects has been provided, initialize the serializer with many=True
        if isinstance(kwargs.get("data", {}), list):
            kwargs["many"] = True

        return super(ModelViewSet, self).get_serializer(*args, **kwargs)


class FieldChoicesViewSet(ViewSet):
    """
    Expose the built-in numeric values which represent static choices for a model's field.
    """

    permission_classes = [IsAuthenticatedOrLoginNotRequired]
    fields = []

    def __init__(self, *args, **kwargs):
        super(FieldChoicesViewSet, self).__init__(*args, **kwargs)

        # Compile a dict of all fields in this view
        self._fields = OrderedDict()
        for cls, field_list in self.fields:
            for field_name in field_list:
                model_name = cls._meta.verbose_name.lower().replace(" ", "-")
                key = ":".join([model_name, field_name])
                choices = []
                for k, v in cls._meta.get_field(field_name).choices:
                    if type(v) in [list, tuple]:
                        for k2, v2 in v:
                            choices.append({"value": k2, "label": v2})
                    else:
                        choices.append({"value": k, "label": v})
                self._fields[key] = choices

    def list(self, request):
        return Response(self._fields)

    def retrieve(self, request, pk):
        if pk not in self._fields:
            raise Http404
        return Response(self._fields[pk])

    def get_view_name(self):
        return "Field Choices"
