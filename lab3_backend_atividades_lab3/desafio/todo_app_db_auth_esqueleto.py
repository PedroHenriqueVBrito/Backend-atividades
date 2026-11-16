import os
import sqlite3
from functools import wraps

from flask import Flask, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
app.config["DATABASE"] = os.environ.get(
    "TODO_DATABASE", os.path.join(os.path.dirname(__file__), "tarefas.db")
)


def conectar_banco():
    """Abre uma conexão SQLite para a requisição atual."""
    if "banco" not in g:
        g.banco = sqlite3.connect(app.config["DATABASE"])
        g.banco.row_factory = sqlite3.Row
        g.banco.execute("PRAGMA foreign_keys = ON")
    return g.banco


@app.teardown_appcontext
def fechar_banco(_erro=None):
    banco = g.pop("banco", None)
    if banco is not None:
        banco.close()


def inicializar_banco():
    """Cria as tabelas caso ainda não existam."""
    banco = conectar_banco()
    banco.executescript(
        """
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            concluida INTEGER NOT NULL DEFAULT 0 CHECK (concluida IN (0, 1)),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
        );
        """
    )
    banco.commit()


def tarefa_para_json(tarefa):
    return {
        "id": tarefa["id"],
        "titulo": tarefa["titulo"],
        "concluida": bool(tarefa["concluida"]),
    }


def usuario_atual_id():
    return session.get("usuario_id")


def exigir_login(funcao):
    @wraps(funcao)
    def decorada(*args, **kwargs):
        if usuario_atual_id() is None:
            return jsonify({"erro": "Autenticação necessária"}), 401
        return funcao(*args, **kwargs)

    return decorada


def obter_json():
    if not request.is_json:
        return None, (jsonify({"erro": "Content-Type deve ser application/json"}), 415)
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, (jsonify({"erro": "O corpo deve ser um objeto JSON"}), 400)
    return dados, None


def validar_titulo(dados):
    titulo = dados.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        return None
    return titulo.strip()


def validar_concluida(valor):
    return isinstance(valor, bool)


@app.route("/cadastro", methods=["POST"])
def cadastrar():
    dados, erro = obter_json()
    if erro:
        return erro

    usuario = dados.get("usuario")
    senha = dados.get("senha")
    if not isinstance(usuario, str) or not usuario.strip():
        return jsonify({"erro": "O campo usuario é obrigatório"}), 400
    if not isinstance(senha, str) or not senha:
        return jsonify({"erro": "O campo senha é obrigatório"}), 400

    usuario = usuario.strip()
    banco = conectar_banco()
    try:
        cursor = banco.execute(
            "INSERT INTO usuarios (usuario, senha_hash) VALUES (?, ?)",
            (usuario, generate_password_hash(senha)),
        )
        banco.commit()
    except sqlite3.IntegrityError:
        return jsonify({"erro": "Usuário já cadastrado"}), 409

    return jsonify({"id": cursor.lastrowid, "usuario": usuario}), 201


@app.route("/login", methods=["POST"])
def login():
    dados, erro = obter_json()
    if erro:
        return erro

    usuario = dados.get("usuario")
    senha = dados.get("senha")
    if not isinstance(usuario, str) or not isinstance(senha, str):
        return jsonify({"erro": "Usuario e senha são obrigatórios"}), 400

    banco = conectar_banco()
    registro = banco.execute(
        "SELECT id, usuario, senha_hash FROM usuarios WHERE usuario = ?",
        (usuario.strip(),),
    ).fetchone()
    if registro is None or not check_password_hash(registro["senha_hash"], senha):
        return jsonify({"erro": "Usuário ou senha inválidos"}), 401

    session.clear()
    session["usuario_id"] = registro["id"]
    session["usuario"] = registro["usuario"]
    return jsonify({"mensagem": "Login realizado", "usuario": registro["usuario"]}), 200


@app.route("/perfil", methods=["GET"])
@exigir_login
def perfil():
    banco = conectar_banco()
    registro = banco.execute(
        "SELECT id, usuario FROM usuarios WHERE id = ?", (usuario_atual_id(),)
    ).fetchone()
    if registro is None:
        session.clear()
        return jsonify({"erro": "Usuário não encontrado"}), 401
    return jsonify({"id": registro["id"], "usuario": registro["usuario"]}), 200


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"mensagem": "Logout realizado"}), 200


@app.route("/tarefas", methods=["GET"])
@exigir_login
def listar_tarefas():
    banco = conectar_banco()
    tarefas = banco.execute(
        """
        SELECT id, titulo, concluida
        FROM tarefas
        WHERE usuario_id = ?
        ORDER BY id
        """,
        (usuario_atual_id(),),
    ).fetchall()
    return jsonify([tarefa_para_json(tarefa) for tarefa in tarefas]), 200


@app.route("/tarefas/<int:tarefa_id>", methods=["GET"])
@exigir_login
def buscar_tarefa(tarefa_id):
    banco = conectar_banco()
    tarefa = banco.execute(
        """
        SELECT id, titulo, concluida
        FROM tarefas
        WHERE id = ? AND usuario_id = ?
        """,
        (tarefa_id, usuario_atual_id()),
    ).fetchone()
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify(tarefa_para_json(tarefa)), 200


@app.route("/tarefas", methods=["POST"])
@exigir_login
def criar_tarefa():
    dados, erro = obter_json()
    if erro:
        return erro

    titulo = validar_titulo(dados)
    if titulo is None:
        return jsonify({"erro": "O campo titulo é obrigatório"}), 400

    concluida = dados.get("concluida", False)
    if not validar_concluida(concluida):
        return jsonify({"erro": "O campo concluida deve ser booleano"}), 400

    banco = conectar_banco()
    cursor = banco.execute(
        """
        INSERT INTO tarefas (usuario_id, titulo, concluida)
        VALUES (?, ?, ?)
        """,
        (usuario_atual_id(), titulo, int(concluida)),
    )
    banco.commit()
    tarefa = {
        "id": cursor.lastrowid,
        "titulo": titulo,
        "concluida": concluida,
    }
    return jsonify(tarefa), 201


@app.route("/tarefas/<int:tarefa_id>", methods=["PUT"])
@exigir_login
def atualizar_tarefa(tarefa_id):
    dados, erro = obter_json()
    if erro:
        return erro
    if not dados:
        return jsonify({"erro": "Informe ao menos um campo para atualizar"}), 400
    if "id" in dados:
        return jsonify({"erro": "O id não pode ser alterado"}), 400
    campos = []
    valores = []

    if "titulo" in dados:
        titulo = validar_titulo(dados)
        if titulo is None:
            return jsonify({"erro": "O campo titulo não pode ser vazio"}), 400
        campos.append("titulo = ?")
        valores.append(titulo)
    if "concluida" in dados:
        if not validar_concluida(dados["concluida"]):
            return jsonify({"erro": "O campo concluida deve ser booleano"}), 400
        campos.append("concluida = ?")
        valores.append(int(dados["concluida"]))

    if not campos:
        return jsonify({"erro": "Campos permitidos: titulo e concluida"}), 400

    valores.extend([tarefa_id, usuario_atual_id()])
    banco = conectar_banco()
    cursor = banco.execute(
        f"UPDATE tarefas SET {', '.join(campos)} WHERE id = ? AND usuario_id = ?",
        valores,
    )
    banco.commit()
    if cursor.rowcount == 0:
        return jsonify({"erro": "Tarefa não encontrada"}), 404

    tarefa = banco.execute(
        "SELECT id, titulo, concluida FROM tarefas WHERE id = ? AND usuario_id = ?",
        (tarefa_id, usuario_atual_id()),
    ).fetchone()
    return jsonify(tarefa_para_json(tarefa)), 200


@app.route("/tarefas/<int:tarefa_id>", methods=["DELETE"])
@exigir_login
def remover_tarefa(tarefa_id):
    banco = conectar_banco()
    cursor = banco.execute(
        "DELETE FROM tarefas WHERE id = ? AND usuario_id = ?",
        (tarefa_id, usuario_atual_id()),
    )
    banco.commit()
    if cursor.rowcount == 0:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return "", 204


with app.app_context():
    inicializar_banco()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
