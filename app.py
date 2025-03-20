from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///estoque.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelos
class Estoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), nullable=False)

class Celula(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    linha = db.Column(db.Integer, nullable=False)
    coluna = db.Column(db.Integer, nullable=False)
    estoque = db.relationship('Estoque', backref='celulas')

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    celula_id = db.Column(db.Integer, db.ForeignKey('celula.id'), nullable=False)
    caixa_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=True)  # Vincula itens/packlists a uma caixa
    projeto_id = db.Column(db.String(50), nullable=False)
    ordem_id = db.Column(db.String(50), nullable=False)
    produto_id = db.Column(db.String(50), nullable=True)  # Opcional para itens normais, obrigatório para packlist items
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    unidade = db.Column(db.String(20), nullable=True)  # Opcional para itens normais, obrigatório para packlist items
    tipo = db.Column(db.String(20), default='item')  # 'item', 'packlist' ou 'caixa'
    data_adicionado = db.Column(db.DateTime, default=db.func.current_timestamp())
    packlist_items = db.relationship('PacklistItem', backref='packlist', lazy=True)
    itens_na_caixa = db.relationship('Item', backref=db.backref('caixa', remote_side=[id]), lazy=True)

class PacklistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    packlist_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    projeto_id = db.Column(db.String(50), nullable=False)
    ordem_id = db.Column(db.String(50), nullable=False)
    produto_id = db.Column(db.String(50), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    unidade = db.Column(db.String(20), nullable=False)

# Função para validar números
def validar_numero(valor):
    return re.match(r'^\d+$', valor) is not None

# Rotas
@app.route('/')
def index():
    estoques = Estoque.query.all()
    ordem_id = request.args.get('ordem_id')
    projeto_id = request.args.get('projeto_id')
    resultados = []
    
    if ordem_id or projeto_id:
        query = db.session.query(Item, Celula, Estoque)\
            .join(Celula, Item.celula_id == Celula.id)\
            .join(Estoque, Celula.estoque_id == Estoque.id)
        
        if ordem_id:
            query = query.filter(Item.ordem_id == ordem_id)
        if projeto_id:
            query = query.filter(Item.projeto_id == projeto_id)
            
        resultados = query.all()
    
    return render_template('index.html', estoques=estoques, resultados=resultados, 
                         ordem_id=ordem_id, projeto_id=projeto_id)

@app.route('/estoque/<int:estoque_id>')
def estoque(estoque_id):
    estoque = Estoque.query.get_or_404(estoque_id)
    celulas = Celula.query.filter_by(estoque_id=estoque_id).all()
    return render_template('estoque.html', estoque=estoque, celulas=celulas)

@app.route('/celula/<int:celula_id>', methods=['GET', 'POST'])
def celula(celula_id):
    celula = Celula.query.get_or_404(celula_id)
    if request.method == 'POST':
        tipo = request.form.get('tipo', 'item')
        projeto_id = request.form['projeto_id']
        ordem_id = request.form['ordem_id']
        caixa_id = request.form.get('caixa_id', None)  # Pode ser None se não for dentro de uma caixa
        
        if not validar_numero(projeto_id) or not validar_numero(ordem_id):
            return "Projeto ID e Ordem ID devem ser números.", 400

        if tipo == 'caixa':
            nome = request.form['nome']  # Nome do projeto inserido pelo operador
            print(f"Adicionando caixa: Projeto ID={projeto_id}, Nome={nome}, Celula ID={celula.id}")
            nova_caixa = Item(
                celula_id=celula.id,
                projeto_id=projeto_id,
                ordem_id=ordem_id,
                nome=nome,
                quantidade=1,  # Uma caixa
                tipo='caixa'
            )
            db.session.add(nova_caixa)
            db.session.commit()
        elif tipo == 'item':
            nome = request.form['nome']
            quantidade = request.form['quantidade']
            produto_id = request.form.get('produto_id', '')
            unidade = request.form.get('unidade', '')

            if not validar_numero(quantidade) or (produto_id and not validar_numero(produto_id)):
                return "Quantidade e Produto ID (se fornecido) devem ser números.", 400

            novo_item = Item(
                celula_id=celula.id,
                caixa_id=caixa_id if caixa_id else None,
                projeto_id=projeto_id,
                ordem_id=ordem_id,
                produto_id=produto_id,
                nome=nome,
                quantidade=quantidade,
                unidade=unidade,
                tipo='item'
            )
            db.session.add(novo_item)
            db.session.commit()
        elif tipo == 'packlist':
            quantidade_itens = int(request.form['quantidade_itens'])
            nome = f"Packlist Ordem {ordem_id}"
            packlist = Item(
                celula_id=celula.id,
                caixa_id=caixa_id if caixa_id else None,
                projeto_id=projeto_id,
                ordem_id=ordem_id,
                nome=nome,
                quantidade=quantidade_itens,
                tipo='packlist'
            )
            db.session.add(packlist)
            db.session.flush()  # Gera o ID do packlist antes de adicionar os itens

            for i in range(quantidade_itens):
                projeto_id_item = request.form[f'packlist_projeto_id_{i}']
                ordem_id_item = request.form[f'packlist_ordem_id_{i}']
                produto_id_item = request.form[f'packlist_produto_id_{i}']
                nome_item = request.form[f'packlist_nome_{i}']
                quantidade_item = request.form[f'packlist_quantidade_{i}']
                unidade_item = request.form[f'packlist_unidade_{i}']

                if not (validar_numero(projeto_id_item) and validar_numero(ordem_id_item) and 
                        validar_numero(produto_id_item) and validar_numero(quantidade_item)):
                    return "Todos os IDs e quantidades dos itens da packlist devem ser números.", 400

                packlist_item = PacklistItem(
                    packlist_id=packlist.id,
                    projeto_id=projeto_id_item,
                    ordem_id=ordem_id_item,
                    produto_id=produto_id_item,
                    nome=nome_item,
                    quantidade=quantidade_item,
                    unidade=unidade_item
                )
                db.session.add(packlist_item)
            db.session.commit()
        
        return redirect(url_for('celula', celula_id=celula.id))
    
    itens = Item.query.filter_by(celula_id=celula_id).all()
    return render_template('celula.html', celula=celula, itens=itens)

@app.route('/celula/<int:celula_id>/qr_code', methods=['POST'])
def processar_qr_code(celula_id):
    celula = Celula.query.get_or_404(celula_id)
    qr_data = request.form.get('qr_data')
    
    print(f"Dados brutos recebidos do scanner: '{qr_data}'")
    
    if not qr_data:
        return jsonify({'error': 'Nenhum dado recebido do scanner'}), 400
    
    try:
        partes = [parte.strip() for parte in qr_data.split(" } ")]
        print(f"Partes após split: {partes}")
        
        if len(partes) < 1:  # Para caixa, só esperamos o ID da PEP
            return jsonify({'error': 'Formato de QR-Code inválido: ID da PEP não encontrado'}), 400
        
        # Para itens normais (Produto ID } Nome } Quantidade } Unidade)
        if len(partes) >= 3:
            projeto_id = "0"  # Padrão
            ordem_id = "0"    # Padrão
            produto_id = partes[0] if validar_numero(partes[0]) else ""
            nome = partes[1]
            quantidade = partes[2]
            unidade = partes[3] if len(partes) > 3 else ""

            if not validar_numero(quantidade):
                return jsonify({'error': 'Quantidade deve ser um número'}), 400
            
            print(f"Dados processados (item via QR-Code) - Projeto ID: {projeto_id}, Ordem ID: {ordem_id}, Produto ID: {produto_id}, Nome: {nome}, Quantidade: {quantidade}, Unidade: {unidade}")
            
            return jsonify({
                'projeto_id': projeto_id,
                'ordem_id': ordem_id,
                'produto_id': produto_id,
                'nome': nome,
                'quantidade': quantidade,
                'unidade': unidade,
                'tipo': 'item'
            })
        # Para caixa (apenas ID da PEP via QR-Code)
        else:
            pep_id = partes[0]
            if not validar_numero(pep_id):
                return jsonify({'error': 'ID da PEP deve ser um número'}), 400
            
            print(f"Dados processados (caixa via QR-Code) - PEP ID: {pep_id}")
            
            return jsonify({
                'projeto_id': "0",  # Padrão
                'ordem_id': pep_id,
                'nome': '',  # Campo vazio para o operador preencher
                'quantidade': 1,
                'tipo': 'caixa'
            })
    except Exception as e:
        print(f"Erro ao processar QR-Code: {str(e)}")
        return jsonify({'error': f'Erro ao processar QR-Code: {str(e)}'}), 400

@app.route('/editar_item/<int:item_id>', methods=['GET', 'POST'])
def editar_item(item_id):
    item = Item.query.get_or_404(item_id)
    if request.method == 'POST':
        projeto_id = request.form['projeto_id']
        ordem_id = request.form['ordem_id']
        produto_id = request.form.get('produto_id', '')
        nome = request.form['nome']
        quantidade = request.form['quantidade']
        unidade = request.form.get('unidade', '')

        if not validar_numero(projeto_id) or not validar_numero(ordem_id) or (produto_id and not validar_numero(produto_id)):
            return "Projeto ID, Ordem ID e Produto ID (se fornecido) devem ser números.", 400

        item.projeto_id = projeto_id
        item.ordem_id = ordem_id
        item.produto_id = produto_id
        item.nome = nome
        item.quantidade = quantidade
        item.unidade = unidade
        db.session.commit()
        return redirect(url_for('celula', celula_id=item.celula_id))
    
    return render_template('editar_item.html', item=item)

@app.route('/remover_item/<int:item_id>')
def remover_item(item_id):
    item = Item.query.get_or_404(item_id)
    celula_id = item.celula_id
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('celula', celula_id=celula_id))

def criar_estoques_e_celulas():
    with app.app_context():
        db.create_all()
        if not Estoque.query.first():
            estoques = [Estoque(nome='Estoque A'), Estoque(nome='Estoque B'), Estoque(nome='Estoque C')]
            db.session.add_all(estoques)
            db.session.commit()
            for estoque in Estoque.query.all():
                for linha in range(3):
                    for coluna in range(3):
                        celula = Celula(estoque_id=estoque.id, linha=linha, coluna=coluna)
                        db.session.add(celula)
            db.session.commit()

criar_estoques_e_celulas()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)