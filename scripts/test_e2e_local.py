import httpx as requests
import random

def get_valid_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    for _ in range(2):
        val = sum([(len(cpf) + 1 - i) * v for i, v in enumerate(cpf)]) % 11
        cpf.append(11 - val if val > 1 else 0)
    return ''.join(map(str, cpf))

API_URL = "http://localhost:8000"

print("Logando Admin...")
r = requests.post(f"{API_URL}/auth/login", json={"email": "admin@oficina.com", "senha": "senha123"})
admin_token = r.json()["token"]
headers_admin = {"Authorization": f"Bearer {admin_token}"}

print("Criando Servico Base...")
payload_servico = {
    "nome": "Troca de Óleo E2E",
    "descricao": "Troca de óleo para testes E2E",
    "preco_base": 150.0,
    "tempo_estimado_minutos": 30
}
r = requests.post(f"{API_URL}/servicos", json=payload_servico, headers=headers_admin)
servico_id = r.json()["id"]
print(f"-> Servico ID: {servico_id}")

cpf = get_valid_cpf()
print(f"Criando Cliente, Veiculo e OS via payload Unificado (CPF: {cpf})")

payload_os = {
    "cliente": {
        "nome": "Cliente E2E Completo",
        "email": f"e2e_{cpf}@completo.com",
        "telefone": "11999999999",
        "cpf": cpf,
        "status": "ATIVO"
    },
    "veiculo": {
        "placa": f"XYZ{random.randint(1000,9999)}",
        "marca": "Toyota",
        "modelo": "Corolla",
        "ano": 2022,
        "cor": "Prata",
        "status": "ATIVO"
    },
    "servicos": [
        {
            "servico_id": servico_id,
            "quantidade": 1
        }
    ],
    "pecas": []
}

r = requests.post(f"{API_URL}/ordens-de-servico", json=payload_os, headers=headers_admin)
if r.status_code != 201:
    print("ERRO:", r.text)
else:
    data = r.json()
    print("OS ABERTA COM SUCESSO!")
    print(f"-> Cliente ID: {data['cliente_id']}")
    print(f"-> Veiculo ID: {data['veiculo_id']}")
    print(f"-> OS ID: {data['id']}")
    print(f"-> Status da OS: {data['status']}")
