# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for
import os
import base64

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB por request

# ---- Rutas y carpetas base ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ROSTROS = os.path.join(BASE_DIR, "static", "rostros")
os.makedirs(RUTA_ROSTROS, exist_ok=True)


def normalizar(texto: str) -> str:
    if not texto:
        return "sin_valor"
    return texto.strip().lower().replace(" ", "_")


# --- MENÚ PRINCIPAL ---
@app.route("/menu")
def menu():
    return render_template("menu.html")


# --- INICIO: REDIRIGE AL MENÚ ---
@app.route("/")
def inicio():
    return redirect(url_for("menu"))


# --- REGISTRO DE ESTUDIANTES ---
@app.route("/Alumnos")
def estudiantes():
    return render_template("index.html")


# --- REGISTRO DE PROFESORES ---
@app.route("/profesores")
def profesores():
    return render_template("profesores.html")


# --- REGISTRO DE TRABAJADORES ---
@app.route("/trabajadores")
def trabajadores():
    return render_template("trabajadores.html")


# --- LOGIN ADMINISTRADOR ---
@app.route("/login")
def login():
    return render_template("login.html")


# --- REGISTRO GENERAL (GUARDA HASTA 3 FOTOS) ---
@app.route("/registrar", methods=["POST"])
def registrar():
    # tipo: alumno / profesor / trabajador
    tipo = (request.form.get("tipo") or "alumno").lower()
    nombre = request.form.get("nombre")
    apellidos = request.form.get("apellidos")
    matricula = request.form.get("matricula") or "sin_matricula"
    carrera = request.form.get("carrera")
    semestre = request.form.get("semestre")

    tipo_norm = normalizar(tipo)
    carrera_norm = normalizar(carrera) if tipo_norm == "alumno" else "sin_carrera"

    # carpeta: static/rostros/tipo/carrera/matricula/
    carpeta_persona = os.path.join(RUTA_ROSTROS, tipo_norm, carrera_norm, matricula)
    os.makedirs(carpeta_persona, exist_ok=True)

    # Para alumnos usamos 3 fotos (foto1, foto2, foto3). Para otros, al menos foto1 si quieres.
    fotos_raw = []
    for key in ["foto1", "foto2", "foto3", "foto"]:
        valor = request.form.get(key)
        if valor:
            fotos_raw.append(valor)

    for idx, foto in enumerate(fotos_raw, start=1):
        try:
            foto_data = foto.split(",")[1]
        except IndexError:
            continue
        foto_bytes = base64.b64decode(foto_data)
        ruta_foto = os.path.join(carpeta_persona, f"{idx}.png")
        with open(ruta_foto, "wb") as f:
            f.write(foto_bytes)

    print(f"✅ Registro guardado: {tipo.upper()} - {nombre} {apellidos} ({matricula}) - {carrera}")
    return redirect(url_for("menu"))


# --- BIOMETRÍA ---
@app.route("/biometria", methods=["GET", "POST"])
def biometria():
    if request.method == "GET":
        return render_template("biometria.html", mensaje=None, exito=None)

    # IMPORTAMOS DeepFace AQUÍ DENTRO para que no trabe el arranque
    from deepface import DeepFace

    tipo = (request.form.get("tipo") or "alumno").lower()
    carrera = request.form.get("carrera") if tipo == "alumno" else None
    foto = request.form.get("foto")

    tipo_norm = normalizar(tipo)
    carrera_norm = normalizar(carrera) if tipo_norm == "alumno" else "sin_carrera"

    if not foto:
        return render_template(
            "biometria.html",
            mensaje="No se recibió la foto.",
            exito=False,
        )

    # Carpeta donde están las fotos de ese tipo/carrera
    carpeta_base = os.path.join(RUTA_ROSTROS, tipo_norm, carrera_norm)
    if not os.path.isdir(carpeta_base):
        return render_template(
            "biometria.html",
            mensaje="No hay registros para esa carrera.",
            exito=False,
        )

    # Guardar foto temporal
    temp_path = os.path.join(RUTA_ROSTROS, "captura_temp.png")
    try:
        foto_data = foto.split(",")[1]
        foto_bytes = base64.b64decode(foto_data)
        with open(temp_path, "wb") as f:
            f.write(foto_bytes)
    except Exception as e:
        print("Error procesando foto:", e)
        return render_template(
            "biometria.html",
            mensaje="Error procesando la foto.",
            exito=False,
        )

    acceso_correcto = False
    persona_encontrada = None

    # Recorrer todas las imágenes registradas para ese tipo/carrera
    for root, dirs, files in os.walk(carpeta_base):
        for file in files:
            if not file.lower().endswith(".png"):
                continue

            ruta_registrada = os.path.join(root, file)

            try:
                # Versión ligera, pero con control de distancia
                result = DeepFace.verify(
                    img1_path=temp_path,
                    img2_path=ruta_registrada,
                    model_name="Facenet",
                    detector_backend="opencv",  # más ligero
                    enforce_detection=False,
                )
            except Exception as e:
                print("Error comparando:", e)
                continue

            distancia = result.get("distance", 1.0)
            verificado = result.get("verified", False)

            print("Comparando con:", ruta_registrada,
                  "| distancia:", distancia,
                  "| verificado:", verificado)

            # Aquí decides qué tan estricto: 0.35 es razonable
            if verificado and distancia < 0.35:
                acceso_correcto = True
                persona_encontrada = os.path.basename(root)  # matrícula
                break

        if acceso_correcto:
            break

    if acceso_correcto:
        mensaje = f"ACCESO CONFIRMADO – MATRÍCULA: {persona_encontrada}"
        return render_template(
            "biometria.html",
            exito=True,
            mensaje=mensaje,
        )
    else:
        mensaje = "ACCESO DENEGADO – NO SE ENCONTRÓ COINCIDENCIA."
        return render_template(
            "biometria.html",
            exito=False,
            mensaje=mensaje,
        )


if __name__ == "__main__":
    # Si quieres probar en otro puerto:
    # app.run(debug=True, port=5001)
    app.run(debug=True)
