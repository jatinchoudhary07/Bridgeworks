#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Collect static files (CSS for admin)
python manage.py collectstatic --no-input --clear

# Run migrations (Update database)
python manage.py migrate

# Seed auto-login admin and rich dummy data
python manage.py seed_local_dev
python manage.py seed_dummy_data
