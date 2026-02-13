#!/bin/bash
# Run the Landscape SaaS Django development server

cd "$(dirname "$0")"
exec ./run runserver
