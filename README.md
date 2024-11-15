
# FreeRADIUS IPv6 Prefix Delegation Generator

This script is designed to manage IPv6 prefix delegation using a MySQL database. It supports assigning random prefixes to users, checking for recently revoked prefixes, and revoking prefixes for removed users.

## Features

- Assign IPv6 prefixes to users who don't already have one.
- Revoke prefixes when users are removed from the `radcheck` table.
- Avoid reassigning recently revoked prefixes.
- Supports hierarchical delegation of IPv6 subnets based on parent prefixes.

## Configuration

The script requires a `config.yaml` file with the following structure:

```yaml
database:
  host: "your_database_host"
  port: 3306
  user: "your_username"
  password: "your_password"
  database: "your_database_name"

revocation_period_days: 90

prefixes:
  - parent_prefix: "2001:db8:c000::/34"
    delegation_length: 48
```

- `database`: Connection details for the MySQL database.
- `revocation_period_days`: Number of days after which a revoked prefix can be reassigned.
- `prefixes`: A list of parent prefixes and their respective delegation lengths.

## Requirements

- Python 3.8 or higher
- The following Python libraries:
  - `ipaddress`
  - `datetime`
  - `random`
  - `logging`
  - `pyyaml`
  - `pymysql`

Install dependencies using pip:

```bash
pip3 install -r requirements.txt -U
```

## Usage

1. Create and configure the `config.yaml` file.
2. Run the script:

```bash
python3 app.py
```

## Logging

The script logs important events, including successful prefix assignments and revocations. Logs are displayed on the console in the format:

```txt
YYYY-MM-DD HH:MM:SS - LEVEL - Message
```

## Database Schema

The script interacts with the following database tables:

- **`radcheck`**: Contains user credentials.
- **`radreply`**: Stores assigned IPv6 prefixes.
- **`delegated_prefixes`**: Tracks prefix assignments and revocation dates.

## License

This script is open-source and licensed under the MIT License. See the LICENSE file for details.
