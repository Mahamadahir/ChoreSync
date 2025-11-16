# PowerShell Script to Reset Django PostgreSQL Database securely
# Save this file as reset_db.ps1 in the same directory as manage.py

# Database config
$DB_NAME = "choresync"
$DB_USER = "choresync_user"
$DB_HOST = "localhost"
$DB_PORT = "5432"
$SUPERUSER = "postgres"  # Replace if your PostgreSQL superuser is different

# Securely prompt for password
Write-Host "Enter password for PostgreSQL user '$SUPERUSER':"
$securePassword = Read-Host -AsSecureString
$DB_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))

# Export password as temp environment variable (used only in this session)
$env:PGPASSWORD = $DB_PASSWORD

Write-Host "Dropping database '$DB_NAME' if it exists..."
psql -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "DROP DATABASE IF EXISTS $DB_NAME;"

Write-Host "Creating new database '$DB_NAME' owned by '$DB_USER'..."
psql -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

Write-Host "Granting ALL privileges on '$DB_NAME' to '$DB_USER'..."
psql -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"

Write-Host "Running Django migrations..."
python manage.py migrate

Write-Host "`nDatabase reset complete!"
