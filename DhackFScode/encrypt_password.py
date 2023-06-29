import string
import bcrypt
import base64
import pickle
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

import random


def generate_random_string(length):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


def generate_key(password, salt):
    password_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        iterations=100000,
        backend=default_backend()
    )

    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))

    return key

def encrypt_data(data, key):
    cipher_suite = Fernet(key)
    encrypted_data = cipher_suite.encrypt(bytes(data))
    return encrypted_data

def decrypt_data(encrypted_data, key):
    cipher_suite = Fernet(key)
    decrypted_data = cipher_suite.decrypt(encrypted_data)
    return decrypted_data

def is_strong_password(password):
    # Define the strength criteria
    has_uppercase = any(char.isupper() for char in password)
    has_lowercase = any(char.islower() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(char in string.punctuation for char in password)

    return has_uppercase and has_lowercase and has_digit and has_special

def get_master_password():
    while True:
        password = input("Enter your master password: ")
        confirm_password = input("Confirm your master password: ")
        if password == confirm_password and is_strong_password(password):
            return password
        else:
            print("Passwords do not match or do not meet the strength criteria. Please try again.")
        pass

def save_master_password(password, key, mountpoint):
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    
    access_keys = {
        "master_password": hashed_password,
        "key": key
    }

    access_info = {mountpoint: access_keys}
    # Save keys to a file or database
    with open('C://dhckfs/pw.txt', 'wb') as file:
        pickle.dump(access_info, file)

def verify_master_password(password, mountpoint):
    # Retrieve the hashed password from the file or database
    with open('C://dhckfs/pw.txt', 'rb') as file:
        access_info = pickle.load(file)

    for mount in access_info:
        if mount == mountpoint:
            access_keys = access_info[mount]
            hashed_password = access_keys["master_password"]
    # Verify the password by comparing the hashed versions
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)
    
