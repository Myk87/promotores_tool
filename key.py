import os

def generate_secret_key():
    """
    Genera una clave secreta aleatoria y segura para Flask.
    """
    return os.urandom(24)

# Genera la clave secreta
secret_key = generate_secret_key()

# Convierte la clave a una cadena hexadecimal
secret_key_hex = secret_key.hex()

print("Clave secreta generada:", secret_key_hex)
