# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import os
import base64

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB por request
app.secret_key = "1234567890"

USUARIOS = {
    "admin": "1234"
}

# ---- Rutas y carpetas base ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_ROSTROS = os.path.join(BASE_DIR, "static", "rostros")
os.makedirs(RUTA_ROSTROS, exist_ok=True)


def normalizar(texto: str) -> str:
    if not texto:
        return "sin_valor"
    return texto.strip().lower().replace(" ", "_")


# --- MENÚ ---
@app.route("/menu")
def menu():
    logueado = 'usuario' in session
    usuario = session.get('usuario')
    return render_template("menu.html", logueado=logueado, usuario=usuario)


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


# --- LOGIN ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if 'usuario' in session:
            return redirect(url_for("menu"))
        return render_template("login.html", error=None)

    # POST: procesar formulario
    usuario = request.form.get("usuario")
    password = request.form.get("password")

    if usuario in USUARIOS and USUARIOS[usuario] == password:
        session['usuario'] = usuario
        return redirect(url_for("menu"))
    else:
        return render_template("login.html", error="Usuario o contraseña incorrectos")


# --- LOGOUT ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("menu"))


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

    # Para alumnos usamos 3 fotos (foto1, foto2, foto3). Para otros, al menos foto1 o foto.
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


# --- BIOMETRÍA (PÁGINA) ---
@app.route("/biometria", methods=["GET"])
def biometria():
    # Solo muestra la página, el JS hace las peticiones a /biometria_auto
    return render_template("biometria.html")


# --- BIOMETRÍA AUTOMÁTICA (API JSON) ---
@app.route("/biometria_auto", methods=["POST"])
def biometria_auto():
    from deepface import DeepFace  # import aquí para no trabar el arranque al inicio

    tipo = (request.form.get("tipo") or "alumno").lower()
    carrera = request.form.get("carrera") if tipo == "alumno" else None
    foto = request.form.get("foto")

    tipo_norm = normalizar(tipo)
    carrera_norm = normalizar(carrera) if tipo_norm == "alumno" else "sin_carrera"

    if not foto:
        return jsonify(exito=False, mensaje="No se recibió la foto.")

    carpeta_base = os.path.join(RUTA_ROSTROS, tipo_norm, carrera_norm)
    if not os.path.isdir(carpeta_base):
        return jsonify(exito=False, mensaje="No hay registros para ese tipo/carrera.")

    # Guardar foto temporal
    temp_path = os.path.join(RUTA_ROSTROS, "captura_temp.png")
    try:
        foto_data = foto.split(",")[1]
        foto_bytes = base64.b64decode(foto_data)
        with open(temp_path, "wb") as f:
            f.write(foto_bytes)
    except Exception as e:
        print("Error procesando foto:", e)
        return jsonify(exito=False, mensaje="Error procesando la foto.")

    acceso_correcto = False
    persona_encontrada = None

    for root, dirs, files in os.walk(carpeta_base):
        for file in files:
            if not file.lower().endswith(".png"):
                continue

            ruta_registrada = os.path.join(root, file)

            try:
                result = DeepFace.verify(
                    img1_path=temp_path,
                    img2_path=ruta_registrada,
                    model_name="Facenet",
                    detector_backend="opencv",  # más ligero
                    enforce_detection=False
                )
            except Exception as e:
                print("Error comparando:", e)
                continue

            distancia = result.get("distance", 1.0)
            verificado = result.get("verified", False)

            print("AUTO | comparando con:", ruta_registrada,
                  "| distancia:", distancia,
                  "| verificado:", verificado)

            if verificado and distancia < 0.35:
                acceso_correcto = True
                persona_encontrada = os.path.basename(root)
                break

        if acceso_correcto:
            break

    if acceso_correcto:
        return jsonify(
            exito=True,
            mensaje=f"ACCESO CONFIRMADO – MATRÍCULA: {persona_encontrada}"
        )

    return jsonify(
        exito=False,
        mensaje="ACCESO DENEGADO – NO SE ENCONTRÓ COINCIDENCIA."
    )


if __name__ == "__main__":
    app.run(debug=True)
