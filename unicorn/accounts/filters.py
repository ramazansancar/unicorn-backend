import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from .models import User, UserCard


class UserSearchFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label=_("Search"))
    usercard = django_filters.CharFilter(method="search_card", label=_("Usercard"))

    class Meta:
        model = User
        fields = ["username"]

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset.none()

        if len(value) < 4:
            return queryset.none()

        return queryset.filter(
            Q(username__icontains=value)
            | Q(email=value)
            | Q(first_name__icontains=value)
            | Q(last_name__icontains=value)
        ).distinct()

    def search_card(self, queryset, name, value):
        if not value.strip():
            return queryset.none()

        try:
            card = UserCard.objects.get(value__iexact=value)
        except UserCard.DoesNotExist:
            return queryset.none()

        if not isinstance(card, UserCard):
            return queryset.none()

        return queryset.filter(pk=card.user.id)
