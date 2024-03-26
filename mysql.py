import random
import string

def generar_contraseña(longitud=12):
    caracteres = string.ascii_letters + string.digits + string.punctuation
    contraseña = ''.join(random.choice(caracteres) for i in range(longitud))
    return contraseña

def main():
    longitud_contraseña = int(input("Ingrese la longitud de la contraseña: "))
    contraseña = generar_contraseña(longitud_contraseña)
    print("La contraseña segura generada es:", contraseña)

if __name__ == "__main__":
    main()


#@ra-$,hEi31q2S:9cw_E
