<h1 align="center">UNICORN 🦄</h1>
<p align="center">Unified Net-based Interface for Competition Organization, Rules and News.</p>


## Running locally (with Docker 🐳)
Before running, make sure to create and populate local environment variables. You can copy the provided example file and then modifying default or adding values to blank settings.
```
cp .env.example .env
```

Then, in order to start the development stack, run the following command:
```
docker-compose up -d
```

When running for the first time, or after clearing the database, remember to run the following commands as well:
```
docker-compose exec web python unicorn/manage.py migrate
docker-compose exec web python unicorn/manage.py createsuperuser
```

You should now be able to access the application at http://localhost:8000/

Some apps may also provide seed data. This can be loaded by running the following command with appropriate adjustments to the last argument.
```
docker-compose exec web python unicorn/manage.py loaddata unicorn/seed.json
```



## Contributing
Ensure you have `pre-commit` installed - `brew install pre-commit` (or replace brew with your package manager, such as yum or apt)

Run `pre-commit install` to have it check your staged changes before allowing you to commit. To skip the pre-commit checks (usually not recommended, but helpful when you'd want to save WIP or similar), use `git commit --no-verify`.


# Authentication providers
## Keycloak
1. Set up according to upstream docs: https://python-social-auth.readthedocs.io/en/latest/backends/keycloak.html
2. Create a mapper to get group memberships
   - Go to Clients -> [client name] -> Mappers
   - Click Create
   - Select "Group Membership" for Mapper Type
   - Name the mapper "groups"