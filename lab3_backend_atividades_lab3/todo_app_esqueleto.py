from flask import Flask, jsonify

app = Flask(__name__)

tarefas = [
    {"id": 1, "titulo": "Estudar Flask", "concluida": False},
    {"id": 2, "titulo": "Revisar o desafio", "concluida": True},
]


@app.route('/tarefas')
def listar_tarefas():
    return jsonify(tarefas), 200


@app.route('/tarefas/<int:id>')
def buscar_tarefa(id):
    tarefa = next((tarefa for tarefa in tarefas if tarefa["id"] == id), None)
    if tarefa is None:
        return jsonify({"erro": "Tarefa não encontrada"}), 404
    return jsonify(tarefa), 200


@app.route('/sobre')
def sobre():
    return jsonify({
        "nome": "Aluno responsável",
        "turma": "Não informada",
        "projeto": "Mini API de Tarefas",
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
