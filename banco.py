import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import pg8000.native
from datetime import datetime
import random
import string
from urllib.parse import urlparse, unquote

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

if DB_URL:
    if isinstance(DB_URL, bytes): DB_URL = DB_URL.decode('utf-8')
    parsed_url = urlparse(DB_URL)
    DB_USER = unquote(parsed_url.username) if parsed_url.username else None
    DB_PASS = unquote(parsed_url.password) if parsed_url.password else None
    DB_HOST = parsed_url.hostname
    DB_PORT = parsed_url.port or 5432
    DB_NAME = parsed_url.path.lstrip("/") if parsed_url.path else ""
else:
    DB_USER = DB_PASS = DB_HOST = DB_PORT = DB_NAME = None

USUARIO_ID = None
USUARIO_ROLE = None
USUARIO_NOME = ""

def executar_db(query, params=(), fetchall=False, fetchone=False):
    if not DB_HOST: return False, "Arquivo .env ausente!"
    conn = None
    try:
        conn = pg8000.native.Connection(user=DB_USER, password=DB_PASS, host=DB_HOST, port=DB_PORT, database=DB_NAME)
        if params:
            for i in range(len(params)): query = query.replace("%s", f":v{i}", 1)
            kwargs = {f"v{i}": val for i, val in enumerate(params)}
            res = conn.run(query, **kwargs)
        else:
            res = conn.run(query)
            
        resultado = res if fetchall else (res[0] if res and fetchone else None)
        return True, resultado
    except Exception as e:
        return False, str(e)
    finally:
        if conn: conn.close()

# ==========================================
# LOGIN, REGISTRO E RECUPERAÇÃO
# ==========================================
def login_sistema(username, password):
    global USUARIO_ID, USUARIO_ROLE, USUARIO_NOME
    sucesso, usuario = executar_db("SELECT id, nome, role FROM usuarios WHERE username = %s AND password = %s", (username, password), fetchone=True)
    if sucesso and usuario:
        USUARIO_ID, USUARIO_NOME, USUARIO_ROLE = usuario[0], usuario[1], usuario[2]
        return True, usuario
    return False, "Usuário ou senha inválidos."

def obter_email_usuario():
    sucesso, res = executar_db("SELECT email FROM usuarios WHERE id = %s", (USUARIO_ID,), fetchone=True)
    return res[0] if sucesso and res else ""

def atualizar_perfil(novo_email, nova_senha=None):
    if nova_senha:
        return executar_db("UPDATE usuarios SET email = %s, password = %s WHERE id = %s", (novo_email, nova_senha, USUARIO_ID))
    else:
        return executar_db("UPDATE usuarios SET email = %s WHERE id = %s", (novo_email, USUARIO_ID))

def registrar_novo_usuario(nome, email, username, password):
    try:
        s, r = executar_db("SELECT id FROM usuarios WHERE username = %s OR email = %s", (username, email), fetchone=True)
        if s and r: return False, "Usuário ou E-mail já estão em uso."

        s2, res_id = executar_db("INSERT INTO usuarios (nome, email, username, password, role) VALUES (%s, %s, %s, %s, 'USER') RETURNING id", (nome, email, username, password), fetchone=True)
        novo_id = res_id[0] if isinstance(res_id, (list, tuple)) else res_id

        executar_db("INSERT INTO contas_bancarias (usuario_id, nome) VALUES (%s, 'Carteira (Dinheiro)')", (novo_id,))
        executar_db("INSERT INTO categorias (usuario_id, nome, tipo) VALUES (%s, 'MATERIAIS', 'SAIDA')", (novo_id,))
        
        return True, "Conta criada com sucesso! Você já pode logar."
    except Exception as e:
        return False, str(e)

def redefinir_senha_por_email(email):
    query = "SELECT id, nome FROM usuarios WHERE email = %s"
    sucesso, res = executar_db(query, (email,), fetchone=True)
    if not res: return False, "E-mail não encontrado no sistema."
    
    nova_senha = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    sucesso_db, msg_db = executar_db("UPDATE usuarios SET password = %s WHERE id = %s", (nova_senha, res[0]))
    
    if sucesso_db:
        remetente = os.getenv("EMAIL_USER")
        senha_app = os.getenv("EMAIL_PASS") 
        if remetente and senha_app:
            try:
                msg = MIMEMultipart()
                msg['From'] = remetente
                msg['To'] = email
                msg['Subject'] = "Recuperação de Senha - Meu Ateliê"
                msg.attach(MIMEText(f"Olá {res[1]},\n\nSua nova senha de acesso é: {nova_senha}", 'plain', 'utf-8'))
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(remetente, senha_app)
                server.send_message(msg)
                server.quit()
                return True, "A nova senha foi enviada para o seu e-mail!"
            except Exception:
                pass
        return True, f"Senha alterada para: {nova_senha} (Anote-a!)"
    return False, "Erro ao atualizar a senha."

# ==========================================
# GESTÃO BÁSICA (BANCOS E MOVIMENTAÇÕES)
# ==========================================
def listar_contas_bancarias():
    s, res = executar_db("SELECT nome FROM contas_bancarias WHERE usuario_id = %s ORDER BY nome", (USUARIO_ID,), fetchall=True)
    return [r[0] for r in res] if s else []

def adicionar_movimentacao_avulsa(data, tipo, conta, desc, valor, cat):
    query = "INSERT INTO movimentacoes (usuario_id, data, tipo_movimento, conta_origem, descricao, valor, categoria) VALUES (%s, %s, %s, %s, %s, %s, %s)"
    return executar_db(query, (USUARIO_ID, data, tipo, conta, desc, float(valor), cat))

# ==========================================
# GESTÃO DE FORNECEDORES E CATEGORIAS
# ==========================================
def listar_fornecedores():
    s, res = executar_db("SELECT id, nome FROM fornecedores WHERE usuario_id = %s ORDER BY nome", (USUARIO_ID,), fetchall=True)
    return res if s and res else []

def adicionar_fornecedor(nome):
    return executar_db("INSERT INTO fornecedores (usuario_id, nome) VALUES (%s, %s)", (USUARIO_ID, nome.upper()))

def editar_fornecedor(id_fornecedor, novo_nome):
    return executar_db("UPDATE fornecedores SET nome = %s WHERE id = %s AND usuario_id = %s", (novo_nome.upper(), id_fornecedor, USUARIO_ID))

def deletar_fornecedor(id_fornecedor):
    return executar_db("DELETE FROM fornecedores WHERE id = %s AND usuario_id = %s", (id_fornecedor, USUARIO_ID))

def listar_categorias_por_tipo(tipo):
    s, res = executar_db("SELECT id, nome FROM categorias WHERE usuario_id = %s AND tipo = %s ORDER BY nome", (USUARIO_ID, tipo), fetchall=True)
    return res if s and res else []

def adicionar_categoria(nome, tipo):
    return executar_db("INSERT INTO categorias (usuario_id, nome, tipo) VALUES (%s, %s, %s)", (USUARIO_ID, nome.upper(), tipo))

def editar_categoria(id_categoria, novo_nome):
    return executar_db("UPDATE categorias SET nome = %s WHERE id = %s AND usuario_id = %s", (novo_nome.upper(), id_categoria, USUARIO_ID))

def deletar_categoria(id_categoria):
    return executar_db("DELETE FROM categorias WHERE id = %s AND usuario_id = %s", (id_categoria, USUARIO_ID))

# ==========================================
# GESTÃO DE MATERIAIS
# ==========================================
def listar_materiais():
    query = '''
        SELECT m.id, m.nome, m.unidade_medida, c.nome, m.categoria_id 
        FROM materiais m LEFT JOIN categorias c ON m.categoria_id = c.id
        WHERE m.usuario_id = %s ORDER BY m.nome
    '''
    s, res = executar_db(query, (USUARIO_ID,), fetchall=True)
    return res if s and res else []

def adicionar_material(nome, categoria_id, unidade_medida):
    query = "INSERT INTO materiais (usuario_id, nome, categoria_id, unidade_medida) VALUES (%s, %s, %s, %s)"
    return executar_db(query, (USUARIO_ID, nome.upper(), categoria_id, unidade_medida))

def editar_material(id_material, novo_nome, nova_categoria_id, nova_medida):
    return executar_db("UPDATE materiais SET nome = %s, categoria_id = %s, unidade_medida = %s WHERE id = %s AND usuario_id = %s", 
                       (novo_nome.upper(), nova_categoria_id, nova_medida, id_material, USUARIO_ID))

def deletar_material(id_material):
    return executar_db("DELETE FROM materiais WHERE id = %s AND usuario_id = %s", (id_material, USUARIO_ID))

# ==========================================
# REGISTRO, BUSCA E EDIÇÃO DE COMPRAS
# ==========================================
def registrar_compra_material(data_compra, material_id, fornecedor_id, quantidade, valor_total, conta_origem):
    try:
        if not quantidade or str(quantidade).strip() == "" or float(quantidade) <= 0:
            q_float = 1.0
        else:
            q_float = float(quantidade)
            
        v_float = float(valor_total)
        v_unitario = v_float / q_float
        
        query_compra = "INSERT INTO compras_materiais (usuario_id, data_compra, material_id, fornecedor_id, quantidade, valor_total, valor_unitario) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        s_compra, _ = executar_db(query_compra, (USUARIO_ID, data_compra, material_id, fornecedor_id, q_float, v_float, v_unitario))
        if not s_compra: return False, "Erro ao registar histórico."

        _, mat = executar_db("SELECT nome FROM materiais WHERE id = %s", (material_id,), fetchone=True)
        _, forn = executar_db("SELECT nome FROM fornecedores WHERE id = %s", (fornecedor_id,), fetchone=True)
        
        desc = f"Compra: {mat[0] if mat else 'Material'} ({forn[0] if forn else 'Fornecedor'})"
        s_mov, _ = adicionar_movimentacao_avulsa(data_compra, 'SAIDA', conta_origem, desc, v_float, "MATERIAIS")
        
        if s_mov: return True, f"Sucesso! Custo: R$ {v_unitario:.2f} por unidade/medida."
        return False, "Salvo, mas erro ao descontar do saldo."
    except ValueError:
        return False, "Valores inválidos."

def listar_historico_compras():
    query = '''
        SELECT c.id, c.data_compra, m.nome, f.nome, c.quantidade, c.valor_total, c.valor_unitario, m.unidade_medida, m.id, f.id
        FROM compras_materiais c
        LEFT JOIN materiais m ON c.material_id = m.id
        LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
        WHERE c.usuario_id = %s
        ORDER BY c.data_compra DESC, c.id DESC
    '''
    sucesso, res = executar_db(query, (USUARIO_ID,), fetchall=True)
    return res if sucesso and res else []

def listar_historico_por_material(material_id):
    query = '''
        SELECT c.id, c.data_compra, f.nome, c.quantidade, c.valor_total, c.valor_unitario, f.id
        FROM compras_materiais c
        LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
        WHERE c.material_id = %s AND c.usuario_id = %s
        ORDER BY c.data_compra DESC
    '''
    sucesso, res = executar_db(query, (material_id, USUARIO_ID), fetchall=True)
    return res if sucesso and res else []

def editar_compra_material(id_compra, data_compra, material_id, fornecedor_id, quantidade, valor_total):
    try:
        if not quantidade or str(quantidade).strip() == "" or float(quantidade) <= 0:
            q_float = 1.0
        else:
            q_float = float(quantidade)
            
        v_float = float(valor_total)
        v_unitario = v_float / q_float
        
        query = '''
            UPDATE compras_materiais 
            SET data_compra = %s, material_id = %s, fornecedor_id = %s, quantidade = %s, valor_total = %s, valor_unitario = %s
            WHERE id = %s AND usuario_id = %s
        '''
        return executar_db(query, (data_compra, material_id, fornecedor_id, q_float, v_float, v_unitario, id_compra, USUARIO_ID))
    except ValueError:
        return False, "Valores inválidos."

def deletar_compra_material(id_compra):
    return executar_db("DELETE FROM compras_materiais WHERE id = %s AND usuario_id = %s", (id_compra, USUARIO_ID))

def calcular_gasto_mes_atual():
    hoje = datetime.today()
    query = '''
        SELECT SUM(valor_total) FROM compras_materiais
        WHERE usuario_id = %s AND EXTRACT(MONTH FROM data_compra) = %s AND EXTRACT(YEAR FROM data_compra) = %s
    '''
    sucesso, res = executar_db(query, (USUARIO_ID, hoje.month, hoje.year), fetchone=True)
    return res[0] if sucesso and res and res[0] else 0.0

# ==========================================
# LISTA DE FALTAS
# ==========================================
def _garantir_tabela_lista():
    executar_db('''
        CREATE TABLE IF NOT EXISTS lista_compras (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            item TEXT NOT NULL
        )
    ''')

def listar_itens_falta():
    _garantir_tabela_lista()
    sucesso, res = executar_db("SELECT id, item FROM lista_compras WHERE usuario_id = %s ORDER BY id DESC", (USUARIO_ID,), fetchall=True)
    return res if sucesso and res else []

def adicionar_item_falta(item):
    _garantir_tabela_lista()
    return executar_db("INSERT INTO lista_compras (usuario_id, item) VALUES (%s, %s)", (USUARIO_ID, item.upper()))

def remover_item_falta(id_item):
    _garantir_tabela_lista()
    return executar_db("DELETE FROM lista_compras WHERE id = %s AND usuario_id = %s", (id_item, USUARIO_ID))