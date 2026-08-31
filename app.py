
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'chave-seguranca-dbm24'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///permutas.db' 
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- BANCO DE DADOS ---
class Militar(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rg = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    graduacao = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_escalante = db.Column(db.Boolean, default=False)
    aprovado = db.Column(db.Boolean, default=False) # True para liberados, False pendentes

class Permuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_servico = db.Column(db.Date, nullable=False)
    militar_saida_id = db.Column(db.Integer, db.ForeignKey('militar.id'), nullable=False)
    militar_entrada_id = db.Column(db.Integer, db.ForeignKey('militar.id'), nullable=False)
    status = db.Column(db.String(30), default='Aguardando Escalante')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    
    saida = db.relationship('Militar', foreign_keys=[militar_saida_id])
    entrada = db.relationship('Militar', foreign_keys=[militar_entrada_id])

@login_manager.user_loader
def load_user(user_id):
    return Militar.query.get(int(user_id))

# --- ROTAS ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        user = Militar.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.senha, senha):
            if not user.aprovado and not user.is_escalante:
                flash('Seu cadastro ainda aguarda aprovação do Escalante.')
                return render_template('login.html')
            login_user(user)
            return redirect(url_for('painel'))
        else:
            flash('Acesso negado. Verifique e-mail e senha.')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        rg = request.form.get('rg')
        nome = request.form.get('nome')
        graduacao = request.form.get('graduacao')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        if Militar.query.filter_by(rg=rg).first() or Militar.query.filter_by(email=email).first():
            flash('Erro: Já existe um cadastro com este RG ou E-mail.')
            return redirect(url_for('registro'))
        
        # Auto-cadastros entram pendentes de aprovação
        novo = Militar(rg=rg, nome=nome, graduacao=graduacao, email=email, senha=generate_password_hash(senha), is_escalante=False, aprovado=False)
        db.session.add(novo)
        db.session.commit()
        
        flash('Cadastro realizado com sucesso! Aguarde a liberação do Escalante para acessar o sistema.')
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/painel')
@login_required
def painel():
    if current_user.is_escalante:
        permutas = Permuta.query.order_by(Permuta.data_servico).all()
        militares_cadastrados = Militar.query.all()
        pendentes = Militar.query.filter_by(aprovado=False).all()
    else:
        permutas = Permuta.query.filter((Permuta.militar_saida_id == current_user.id) | (Permuta.militar_entrada_id == current_user.id)).all()
        militares_cadastrados = []
        pendentes = []
    
    # Apenas militares aprovados podem ser escolhidos como substitutos
    militares_ativos = Militar.query.filter(Militar.id != current_user.id, Militar.aprovado == True).all()
    return render_template('painel.html', permutas=permutas, militares=militares_ativos, todos_militares=militares_cadastrados, pendentes=pendentes)

@app.route('/aprovar_militar/<int:id>')
@login_required
def aprovar_militar(id):
    if not current_user.is_escalante:
        return redirect(url_for('painel'))
    m = Militar.query.get_or_404(id)
    m.aprovado = True
    db.session.commit()
    flash(f'Acesso liberado para {m.graduacao} {m.nome}!')
    return redirect(url_for('painel'))

@app.route('/alterar_senha', methods=['POST'])
@login_required
def alterar_senha():
    senha_atual = request.form.get('senha_atual')
    nova_senha = request.form.get('nova_senha')
    
    if not check_password_hash(current_user.senha, senha_atual):
        flash('Erro: A senha atual está incorreta.')
        return redirect(url_for('painel'))
    
    current_user.senha = generate_password_hash(nova_senha)
    db.session.commit()
    flash('Senha alterada com sucesso!')
    return redirect(url_for('painel'))

@app.route('/nova_permuta', methods=['POST'])
@login_required
def nova_permuta():
    data_str = request.form.get('data_servico')
    substituto_id = request.form.get('substituto_id')
    
    data_servico = datetime.strptime(data_str, '%Y-%m-%d').date()
    hoje = datetime.now().date()
    diferenca = (data_servico - hoje).days

    if diferenca < 2:
        flash('ERRO: Solicitação bloqueada (Menos de 48h). Requer liberação do Escalante.')
        return redirect(url_for('painel'))
    
    nova = Permuta(data_servico=data_servico, militar_saida_id=current_user.id, militar_entrada_id=substituto_id)
    db.session.add(nova)
    db.session.commit()
    
    flash('Assinatura digital registrada! Permuta enviada para avaliação do Escalante.')
    return redirect(url_for('painel'))

@app.route('/avaliar_permuta/<int:id>/<acao>')
@login_required
def avaliar_permuta(id, acao):
    if not current_user.is_escalante:
        return redirect(url_for('painel'))
    
    p = Permuta.query.get_or_404(id)
    if acao == 'aprovar':
        p.status = 'Autorizada'
        flash(f'Permuta de {p.data_servico.strftime("%d/%m/%Y")} AUTORIZADA.')
    elif acao == 'negar':
        p.status = 'Recusada'
        flash(f'Permuta de {p.data_servico.strftime("%d/%m/%Y")} recusada.')
        
    db.session.commit()
    return redirect(url_for('painel'))

@app.route('/relatorio/<int:id>')
@login_required
def relatorio(id):
    p = Permuta.query.get_or_404(id)
    return render_template('relatorio.html', p=p)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- INICIALIZAÇÃO ---
with app.app_context():
    db.create_all()
    admin = Militar.query.filter_by(email='escalante@cbmerj.com').first()
    if admin:
        admin.graduacao = '2º Sgt'
        admin.nome = 'L. da Silva'
        admin.aprovado = True
        admin.is_escalante = True
        db.session.commit()
    else:
        # Se não existir, cria o admin padrão
        novo_admin = Militar(rg='00000', nome='L. da Silva', graduacao='2º Sgt', email='escalante@cbmerj.com', senha=generate_password_hash('123456'), is_escalante=True, aprovado=True)
        db.session.add(novo_admin)
        db.session.commit()

    # Aprova automaticamente os 2 testes já cadastrados anteriormente para não trancarem
    for mil in Militar.query.all():
        if mil.email != 'escalante@cbmerj.com':
            mil.aprovado = True
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)