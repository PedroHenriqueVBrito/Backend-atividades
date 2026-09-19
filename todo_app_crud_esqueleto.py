from flask import Flask, jsonify, request

app = Flask(__name__)

tarefas = [
    {"id": 1, "titulo": "Estudar Flask", "concluida": False},
    {"id": 2, "titulo": "Revisar o desafio anterior", "concluida": True},
]
proximo_id = 3


@app.route('/tarefas', methods=['GET'])
def listar_tarefas():
    return jsonify(tarefas), 200


@app.route('/tarefas/<int:id>', methods=['GET'])
def buscar_tarefa(id):
    tarefa = next((t for t in tarefas if t["id"] == id), None)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify(tarefa), 200


@app.route('/tarefas', methods=['POST'])
def criar_tarefa():
    global proximo_id

    if not request.is_json:
        return jsonify({"erro": "Content-Type deve ser application/json"}), 415

    dados = request.get_json()
    if "titulo" not in dados:
        return jsonify({"erro": "O campo titulo é obrigatório"}), 400

    tarefa = {
        "id": proximo_id,
        "titulo": dados["titulo"],
        "concluida": dados.get("concluida", False),
    }
    tarefas.append(tarefa)
    proximo_id += 1

    return jsonify(tarefa), 201


@app.route('/tarefas/<int:id>', methods=['PUT'])
def atualizar_tarefa(id):
    tarefa = next((t for t in tarefas if t["id"] == id), None)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada"}), 404

    if not request.is_json:
        return jsonify({"erro": "Content-Type deve ser application/json"}), 415

    dados = request.get_json()
    for campo, valor in dados.items():
        if campo != "id":
            tarefa[campo] = valor

    return jsonify(tarefa), 200


@app.route('/tarefas/<int:id>', methods=['DELETE'])
def remover_tarefa(id):
    global tarefas

    tarefa = next((t for t in tarefas if t["id"] == id), None)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada"}), 404

    tarefas.remove(tarefa)
    return '', 204


if __name__ == '__main__':
    app.run(debug=True)
