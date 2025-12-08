# PowerShell Script to reset the Django PostgreSQL database using settings-driven env values
# Uses backend\secrets.env (read by chore_sync/settings.py) to avoid hard-coded credentials.

param()

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$envFile = Join-Path $ScriptDir "secrets.env"
if (-not (Test-Path $envFile)) {
    Write-Error "secrets.env not found at $envFile. Create it before running this script."
    exit 1
}

function Get-EnvVarsFromFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )
    $vars = @{}
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $idx = $trimmed.IndexOf("=")
        if ($idx -lt 1) { continue }
        $key = $trimmed.Substring(0, $idx).Trim()
        $value = $trimmed.Substring($idx + 1).Trim()
        $value = $value.Trim("'`"") # strip single/double quotes
        $vars[$key] = $value
    }
    return $vars
}

function Parse-PostgresUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )
    $pattern = '^postgres(?:ql)?:\/\/(?<user>[^:\/\s]+):(?<password>[^@]+)@(?<host>[^:\/\s]+)(?::(?<port>\d+))?\/(?<dbname>[^?\s]+)'
    if ($Url -notmatch $pattern) {
        throw "DATABASE_URL is not a valid postgres URL: $Url"
    }
    return @{
        User     = $Matches.user
        Password = $Matches.password
        Host     = $Matches.host
        Port     = if ($Matches.port) { $Matches.port } else { "5432" }
        Name     = $Matches.dbname
    }
}

$envVars = Get-EnvVarsFromFile -Path $envFile
$databaseUrl = $envVars["DATABASE_URL"]
if (-not $databaseUrl) {
    Write-Error "DATABASE_URL not set in secrets.env; required for DB reset."
    exit 1
}

$dbConfig = Parse-PostgresUrl -Url $databaseUrl
$DB_NAME = $dbConfig.Name
$DB_USER = $dbConfig.User
$DB_PASSWORD = $dbConfig.Password
$DB_HOST = $dbConfig.Host
$DB_PORT = $dbConfig.Port

$SUPERUSER = if ($envVars["PG_SUPERUSER"]) { $envVars["PG_SUPERUSER"] } else { "postgres" }
$SUPERUSER_EMAIL = $envVars["PG_SUPERUSER_EMAIL"]
$superPwd = $envVars["PG_SUPERUSER_PASSWORD"]
if (-not $superPwd) {
    Write-Host "Enter password for PostgreSQL user '$SUPERUSER':"
    $securePassword = Read-Host -AsSecureString
    $superPwd = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
}
if ($SUPERUSER_EMAIL) {
    Write-Host "Using PostgreSQL superuser '$SUPERUSER' ($SUPERUSER_EMAIL) from secrets.env"
}

$env:PGPASSWORD = $superPwd

# Ensure role exists with password from secrets.env
$escapedUser = $DB_USER.Replace("'", "''")
$escapedPass = $DB_PASSWORD.Replace("'", "''")
$roleSql = @"
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$escapedUser') THEN
        EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '$escapedUser', '$escapedPass');
    ELSE
        EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '$escapedUser', '$escapedPass');
    END IF;
END
$$;
"@

Write-Host "Ensuring role '$DB_USER' exists and password matches secrets.env..."
psql -v ON_ERROR_STOP=1 -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "$roleSql"

$escapedDbName = $DB_NAME.Replace('"', '""')
$escapedDbUser = $DB_USER.Replace('"', '""')

Write-Host "Dropping database '$DB_NAME' if it exists..."
psql -v ON_ERROR_STOP=1 -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "DROP DATABASE IF EXISTS ""$escapedDbName"";"

Write-Host "Creating new database '$DB_NAME' owned by '$DB_USER'..."
psql -v ON_ERROR_STOP=1 -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "CREATE DATABASE ""$escapedDbName"" OWNER ""$escapedDbUser"";"

Write-Host "Granting ALL privileges on '$DB_NAME' to '$DB_USER'..."
psql -v ON_ERROR_STOP=1 -U $SUPERUSER -h $DB_HOST -p $DB_PORT -c "GRANT ALL PRIVILEGES ON DATABASE ""$escapedDbName"" TO ""$escapedDbUser"";"

Write-Host "Running Django migrations using settings.py + secrets.env..."
python manage.py migrate

# Create Django superuser from secrets.env if provided
$djSuUser = $envVars["DJANGO_SUPERUSER_USERNAME"]
$djSuEmail = $envVars["DJANGO_SUPERUSER_EMAIL"]
$djSuPassword = $envVars["DJANGO_SUPERUSER_PASSWORD"]
if ($djSuUser -and $djSuEmail -and $djSuPassword) {
    Write-Host "Ensuring Django superuser '$djSuUser' exists..."
    $pyCmd = "from django.contrib.auth import get_user_model; User = get_user_model(); username = '$djSuUser'; email = '$djSuEmail'; password = '$djSuPassword'; user, created = User.objects.get_or_create(username=username, defaults={'email': email}); user.email = email; user.is_superuser = True; user.is_staff = True; user.set_password(password); user.save(); print('created' if created else 'updated')"
    python manage.py shell -c "$pyCmd"
} else {
    Write-Host "Skipping Django superuser creation; missing DJANGO_SUPERUSER_* entries in secrets.env"
}

Write-Host "`nDatabase reset complete!"
