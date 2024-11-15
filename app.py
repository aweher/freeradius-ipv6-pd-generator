import os
import random
import time
import logging
from ipaddress import IPv6Network
from datetime import datetime, timedelta
import yaml
import pymysql


# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DatabaseConnection:
    def __init__(self, db_config):
        self.db_config = db_config
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.connection = None

    def __enter__(self):
        self.connection = pymysql.connect(
            host=self.db_config['host'],
            user=self.db_config['user'],
            port=self.db_config['port'],
            password=self.db_config['password'],
            database=self.db_config['database']
        )
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()

class IPv6PrefixManager:
    def __init__(self, config_path):
        self.config = self.load_config(config_path)
        self.db_config = self.config['database']
        self.revocation_period_days = self.config['revocation_period_days']
    
    @staticmethod
    def load_config(file_path):
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.path.dirname(__file__), file_path)
        with open(file_path, 'r') as f:
            return yaml.safe_load(f)
    
    def is_recently_revoked(self, cursor, delegated_prefix):
        cursor.execute("""
            SELECT revoked_date FROM delegated_prefixes 
            WHERE delegated_prefix = %s AND revoked_date IS NOT NULL
        """, (delegated_prefix,))
        result = cursor.fetchone()
        if result:
            revoked_date = result[0]
            return (datetime.now().date() - revoked_date) < timedelta(days=self.revocation_period_days)
        return False

    def is_prefix_assigned(self, cursor, delegated_prefix):
        cursor.execute("SELECT * FROM radreply WHERE value = %s", (delegated_prefix,))
        if cursor.fetchone():
            return True
        cursor.execute("SELECT * FROM delegated_prefixes WHERE delegated_prefix = %s", (delegated_prefix,))
        return cursor.fetchone() is not None

    def get_random_available_prefix(self, cursor, parent_prefix, delegation_length):
        parent_net = IPv6Network(parent_prefix)
        subnets = list(parent_net.subnets(new_prefix=delegation_length))
        random.shuffle(subnets)

        for subnet in subnets:
            delegated_prefix = str(subnet)
            if not self.is_prefix_assigned(cursor, delegated_prefix) and not self.is_recently_revoked(cursor, delegated_prefix):
                if self.is_subnet_of(parent_prefix, delegated_prefix):
                    return delegated_prefix
        return None

    @staticmethod
    def is_subnet_of(supernet, subnet):
        supernet = IPv6Network(supernet)
        subnet = IPv6Network(subnet)
        return subnet.subnet_of(supernet)

    def insert_delegated_prefix(self, cursor, username, delegated_prefix):
        assigned_date = datetime.now().date()
        try:
            cursor.execute(
                "INSERT INTO delegated_prefixes (username, delegated_prefix, assigned_date) VALUES (%s, %s, %s)",
                (username, delegated_prefix, assigned_date)
            )
            cursor.execute(
                "INSERT INTO radreply (username, attribute, op, value) VALUES (%s, 'Delegated-IPv6-Prefix', '=', %s)",
                (username, delegated_prefix)
            )
        except pymysql.MySQLError as e:
            logging.error(f"Error inserting delegated prefix {delegated_prefix} for {username}: {e}")
            raise

    def mark_prefix_as_revoked(self, cursor, username):
        revoked_date = datetime.now().date()
        try:
            cursor.execute("""
                UPDATE delegated_prefixes 
                SET revoked_date = %s 
                WHERE username = %s AND revoked_date IS NULL
            """, (revoked_date, username))
            logging.info(f"Revoked prefix for {username} on {revoked_date}")
        except pymysql.MySQLError as e:
            logging.error(f"Error revoking prefix for {username}: {e}")
            raise

    def get_users_without_prefix(self, cursor):
        cursor.execute("""
            SELECT DISTINCT(username) FROM radcheck 
            WHERE attribute = 'Cleartext-Password' 
            AND username NOT IN (SELECT username FROM delegated_prefixes)
        """)
        return cursor.fetchall()

    def get_removed_users(self, cursor):
        cursor.execute("""
            SELECT username FROM delegated_prefixes 
            WHERE username NOT IN (SELECT username FROM radcheck) AND revoked_date IS NULL
        """)
        return cursor.fetchall()

    def process_prefix_assignments(self):
        with DatabaseConnection(self.db_config) as db:
            with db.cursor() as cursor:
                # Marcar prefijos como revocados para usuarios eliminados de radcheck
                removed_users = self.get_removed_users(cursor)
                for (username,) in removed_users:
                    self.mark_prefix_as_revoked(cursor, username)

                # Asignar nuevos prefijos para usuarios sin asignaciones
                for prefix_entry in self.config['prefixes']:
                    parent_prefix = prefix_entry['parent_prefix']
                    delegation_length = prefix_entry['delegation_length']

                    users = self.get_users_without_prefix(cursor)

                    for username, in users:
                        delegated_prefix = self.get_random_available_prefix(cursor, parent_prefix, delegation_length)
                        if delegated_prefix:
                            self.insert_delegated_prefix(cursor, username, delegated_prefix)
                            logging.info(f"Delegated prefix {delegated_prefix} assigned to {username}")
                        else:
                            logging.warning(f"No available prefix for {username}")

                db.commit()

if __name__ == "__main__":
    manager = IPv6PrefixManager('config.yaml')
    
    # Get sleep interval from config, default to 300 if not specified
    sleep_interval = manager.config.get('sleep_interval_seconds', 300)
    
    logging.info(f"Starting IPv6 prefix delegation service with {sleep_interval} seconds interval")
    
    while True:
        try:
            manager.process_prefix_assignments()
            logging.info(f"Sleeping for {sleep_interval} seconds...")
            time.sleep(sleep_interval)
        except KeyboardInterrupt:
            logging.info("Service stopped by user")
            break
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            time.sleep(sleep_interval)  # Still sleep on error to prevent rapid retries