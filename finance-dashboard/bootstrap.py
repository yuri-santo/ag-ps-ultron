"""Create an isolated database from the public schema and optional fictional data."""
import argparse
from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3


SCHEMA = '''
CREATE TABLE config(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE login_attempts(ip TEXT PRIMARY KEY, tentativas INTEGER DEFAULT 0, bloqueado_ate TEXT, ultima_tentativa TEXT);
CREATE TABLE contas_a_pagar(id INTEGER PRIMARY KEY, descricao TEXT, beneficiario TEXT, categoria TEXT, valor REAL DEFAULT 0, vencimento TEXT, status TEXT DEFAULT 'A Vencer', cartao TEXT DEFAULT 'Conta');
CREATE TABLE gastos_fatura(id INTEGER PRIMARY KEY, data TEXT, descricao TEXT, categoria TEXT, valor REAL DEFAULT 0, tipo TEXT, parcela_atual INTEGER DEFAULT 1, parcela_total INTEGER DEFAULT 1, data_lancamento TEXT, mes_ref TEXT);
CREATE TABLE cartoes_credito(id INTEGER PRIMARY KEY, nome TEXT, bandeira TEXT, limite REAL DEFAULT 0, dia_fechamento INTEGER DEFAULT 20, dia_vencimento INTEGER DEFAULT 28, ativo INTEGER DEFAULT 1);
CREATE TABLE faturas_fechadas(cartao TEXT, mes TEXT, valor REAL NOT NULL, PRIMARY KEY(cartao,mes));
CREATE TABLE compras_parceladas(id INTEGER PRIMARY KEY, descricao TEXT, categoria TEXT, valor_parcela REAL DEFAULT 0, parcela_atual INTEGER DEFAULT 1, parcela_total INTEGER DEFAULT 1, valor_total REAL DEFAULT 0, vencimento_dia INTEGER DEFAULT 28);
CREATE TABLE assinaturas(id INTEGER PRIMARY KEY, nome TEXT, valor REAL DEFAULT 0, frequencia TEXT DEFAULT 'mensal', dia_do_mes INTEGER DEFAULT 1, cartao TEXT DEFAULT 'Conta', ativa INTEGER DEFAULT 1);
CREATE TABLE metas(id INTEGER PRIMARY KEY, nome TEXT, valor_alvo REAL DEFAULT 0, valor_atual REAL DEFAULT 0, data_alvo TEXT, ativa INTEGER DEFAULT 1);
CREATE TABLE carteira_real(id INTEGER PRIMARY KEY, ticker TEXT, nome TEXT, classe TEXT, quantidade REAL DEFAULT 0, preco_medio REAL DEFAULT 0, preco_atual REAL DEFAULT 0, data_entrada TEXT);
CREATE TABLE horas_receber(id INTEGER PRIMARY KEY, mes TEXT, descricao TEXT, horas REAL DEFAULT 0, valor REAL DEFAULT 0, status TEXT DEFAULT 'Pendente', data_recebimento TEXT);
CREATE TABLE tickets_pagamento(id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, cliente TEXT, descricao TEXT, status TEXT, horas REAL DEFAULT 0, valor REAL DEFAULT 0, valor_hora REAL DEFAULT 0, data_estimada_pgto TEXT, status_pgto TEXT, criado_em TEXT);
CREATE TABLE horas_mensal(mes TEXT PRIMARY KEY, total_hours REAL DEFAULT 0);
CREATE TABLE caixinhas(id INTEGER PRIMARY KEY, nome TEXT, meta REAL DEFAULT 0, descricao TEXT);
CREATE TABLE caixinhas_movimentos(id INTEGER PRIMARY KEY, caixinha_id INTEGER, mes TEXT, valor REAL DEFAULT 0, tipo TEXT, obs TEXT, data_registro TEXT);
CREATE TABLE moradia(id INTEGER PRIMARY KEY, regiao TEXT, total_mensal REAL DEFAULT 0);
CREATE TABLE insights(id INTEGER PRIMARY KEY, data TEXT, tipo TEXT, titulo TEXT, texto TEXT, origem TEXT, lido INTEGER DEFAULT 0);
'''


def create_database(path, demo=False):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidentally replacing a personal database.
    with path.open('xb'):
        pass
    try:
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript(SCHEMA)
            db.execute('INSERT INTO config VALUES (?,?)', ('dataset', 'synthetic' if demo else 'empty'))
            if demo:
                seed_demo(db)
    except Exception:
        path.unlink()
        raise
    return path


def seed_demo(db):
    month = date.today().strftime('%Y-%m')
    today = month + '-05'
    values = {'salario': '6400', 'horas_base_mes': '80', 'valor_hora_extra': '85'}
    db.executemany('INSERT INTO config VALUES (?,?)', values.items())
    db.executemany('INSERT INTO contas_a_pagar(descricao,beneficiario,categoria,valor,vencimento,status,cartao) VALUES (?,?,?,?,?,?,?)', [
        ('Moradia demonstrativa', 'Fornecedor ficticio A', 'Moradia', 1350, month+'-10', 'Pago', 'Conta'),
        ('Mercado demonstrativo', 'Fornecedor ficticio B', 'Alimentacao', 620, month+'-15', 'A Vencer', 'Pix'),
        ('Conexao demonstrativa', 'Fornecedor ficticio C', 'Servicos', 95, month+'-20', 'A Vencer', 'Conta')])
    db.execute('INSERT INTO cartoes_credito(nome,bandeira,limite) VALUES (?,?,?)', ('Cartao Demo', 'Visa', 4200))
    db.execute('INSERT INTO faturas_fechadas VALUES (?,?,?)', ('Cartao Demo', month, 275))
    db.execute('INSERT INTO compras_parceladas(descricao,categoria,valor_parcela,parcela_atual,parcela_total,valor_total) VALUES (?,?,?,?,?,?)', ('Equipamento demonstrativo', 'Cartao Demo', 150, 2, 6, 900))
    db.execute('INSERT INTO assinaturas(nome,valor,cartao) VALUES (?,?,?)', ('Software demonstrativo', 45, 'Cartao Demo'))
    db.execute('INSERT INTO gastos_fatura(data,descricao,categoria,valor,tipo,data_lancamento,mes_ref) VALUES (?,?,?,?,?,?,?)', (today, 'Compra demonstrativa', 'Equipamento', 80, 'Debito', today, month))
    db.execute('INSERT INTO horas_receber(mes,descricao,horas,valor,status,data_recebimento) VALUES (?,?,?,?,?,?)', (month, 'Contrato demonstrativo', 80, 6400, 'Pago', today))
    db.execute('INSERT INTO tickets_pagamento(data,tipo,cliente,descricao,status,horas,valor,valor_hora,data_estimada_pgto,status_pgto,criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (today, 'Extra', 'Cliente Ficticio', 'Site demonstrativo', 'Realizado', 4, 340, 85, month, 'PENDENTE', today))
    db.execute('INSERT INTO horas_mensal VALUES (?,?)', (month, 84))
    db.execute('INSERT INTO metas(nome,valor_alvo,valor_atual,data_alvo) VALUES (?,?,?,?)', ('Reserva demonstrativa', 12000, 1800, f'{date.today().year+1}-12-01'))
    db.execute('INSERT INTO caixinhas(nome,meta,descricao) VALUES (?,?,?)', ('Reserva demonstrativa', 12000, 'Exemplo ficticio'))
    db.execute('INSERT INTO caixinhas_movimentos(caixinha_id,mes,valor,tipo,obs,data_registro) VALUES (?,?,?,?,?,?)', (1, month, 1800, 'deposito', 'Exemplo ficticio', today))
    db.execute('INSERT INTO moradia(regiao,total_mensal) VALUES (?,?)', ('Regiao demonstrativa', 1800))
    db.execute('INSERT INTO carteira_real(ticker,nome,classe,quantidade,preco_medio,preco_atual,data_entrada) VALUES (?,?,?,?,?,?,?)', ('DEMO', 'Ativo ficticio sem cotacao', 'Exemplo', 10, 20, 21, today))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/finance-demo.db')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    print(create_database(args.db, args.demo))
