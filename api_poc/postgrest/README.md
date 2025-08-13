# PostgREST Setup for PharmChecker

## Installation

Install PostgREST binary:

```bash
# Download latest release
wget https://github.com/PostgREST/postgrest/releases/download/v12.0.2/postgrest-v12.0.2-linux-static-x64.tar.xz
tar -xf postgrest-v12.0.2-linux-static-x64.tar.xz
sudo mv postgrest /usr/local/bin/
```

## Running

Start PostgREST server:

```bash
cd api_poc/postgrest
postgrest postgrest.conf
```

The API will be available at http://localhost:3000

## Configuration

- Database connection configured to use existing pharmchecker database
- Default role: postgres
- Port: 3000
- Schema: public

## Testing

Check if API is running:
```bash
curl http://localhost:3000/
```

List available tables:
```bash
curl http://localhost:3000/datasets
```