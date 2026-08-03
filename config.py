import os
from pathlib import Path
from environs import Env

# todo: With environs take .env file datas
env = Env()
# Open .env file in core/envs folder
if os.path.exists('.env'):
    env.read_env(str(Path(__file__).resolve().parent / '.env'))
else:
    print('.env file not found!')
    print('Copy .env.example  and fill it with your data!')
    exit(1)


# todo: .env file datas
HEMIS_TOKEN = env.str('HEMIS_TOKEN')
LOGIN_VALUE = env.str('LOGIN_VALUE')
PASSWORD_VALUE = env.str('PASSWORD_VALUE')
BILLING_LOGIN_VALUE = env.str('BILLING_LOGIN_VALUE')
BILLING_PASSWORD_VALUE = env.str('BILLING_PASSWORD_VALUE')
BILLING_N_LOGIN_VALUE = env.str('BILLING_N_LOGIN_VALUE')
BILLING_N_PASSWORD_VALUE = env.str('BILLING_N_PASSWORD_VALUE')
