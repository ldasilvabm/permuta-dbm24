from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'

if 'RENDER' in os.environ:
    db_path = '/tmp/database.db'
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'database.db')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    graduacao = db.Column(db.String(50), nullable=False)
    rg = db.Column(db.String(20), unique=True, nullable=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)
class Permuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    substituto_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data_servico = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pendente')

    solicitante = db.relationship('User', foreign_keys=[solicitante_id])
    substituto = db.relationship('User', foreign_keys=[substituto_id])
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.senha, senha):
            if not user.is_approved:
                flash('Sua conta aguarda aprovação do Escalante.', 'warning')
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('painel'))
        else:
            flash('E-mail ou senha incorretos.', 'danger')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        graduacao = request.form.get('graduacao')
        rg = request.form.get('rg')
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        user_exist = User.query.filter_by(email=email).first()
        if user_exist:
            flash('Este e-mail já está cadastrado.', 'danger')
            return redirect(url_for('registro'))
        
        total_users = User.query.count()
        is_first = (total_users == 0)
        
        hashed_password = generate_password_hash(senha, method='pbkdf2:sha256')
        new_user = User(
            nome=nome, 
            graduacao=graduacao, 
            rg=rg,
            email=email, 
            senha=hashed_password,
            is_admin=is_first,
            is_approved=is_first
        )
        db.session.add(new_user)
        db.session.commit()
        
        if is_first:
            flash('Conta de Escalante principal criada com sucesso!', 'success')
        else:
            flash('Cadastro realizado com sucesso! Aguarde a aprovação do Escalante.', 'info')
        return redirect(url_for('login'))
        
    return render_template('registro.html')
class Permuta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    substituto_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data_servico = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='Pendente')

    solicitante = db.relationship('User', foreign_keys=[solicitante_id])
    substituto = db.relationship('User', foreign_keys=[substituto_id])
@app.route('/painel')
@login_required
def painel():
    usuarios_pendentes = []
    todos_usuarios = []
    
    if current_user.is_admin:
        usuarios_pendentes = User.query.filter_by(is_approved=False).all()
        todos_usuarios = User.query.all()
        permutas = Permuta.query.all()  # Escalante vê todas as permutas
    else:
        permutas = Permuta.query.filter(
            (Permuta.solicitante_id == current_user.id) | 
            (Permuta.substituto_id == current_user.id)
        ).all()  # Militar vê apenas as suas

    mitares_aprovados = User.query.filter(User.is_approved == True, User.id != current_user.id).all()

    return render_template(
        'painel.html', 
        usuarios_pendentes=usuarios_pendentes, 
        todos_usuarios=todos_usuarios, 
        mitares_aprovados=mitares_aprovados,
        permutas=permutas
    )
@app.route('/aprovar/<int:user_id>')
@login_required
def aprovar(user_id):
    if current_user.is_admin:
        user = db.session.get(User, user_id)
        if user:
            user.is_approved = True
            db.session.commit()
            flash(f'Cadastro de {user.nome} aprovado!', 'success')
    return redirect(url_for('painel'))

@app.route('/toggle_admin/<int:user_id>')
@login_required
def toggle_admin(user_id):
    if current_user.is_admin:
        user = db.session.get(User, user_id)
        if user and user.id != current_user.id:
            user.is_admin = not user.is_admin
            db.session.commit()
            flash(f'Permissões de Escalante atualizadas para {user.nome}.', 'success')
    return redirect(url_for('painel'))
# Rota para Solicitar Permuta
@app.route('/solicitar_permuta', methods=['POST'])
@login_required
def solicitar_permuta():
    try:
        data_servico = request.form.get('data_servico')
        substituto_id = request.form.get('substituto')
        
        if not data_servico or not substituto_id:
            flash('Preencha a data e selecione o militar substituto.', 'danger')
            return redirect(url_for('painel'))
        
        nova_permuta = Permuta(
            solicitante_id=current_user.id,
            substituto_id=int(substituto_id),
            data_servico=data_servico,
            status='Aguardando Substituto'
        )
        db.session.add(nova_permuta)
        db.session.commit()
        
        flash('Permuta solicitada com sucesso! Aguardando assinatura eletrônica do substituto.', 'success')
        return redirect(url_for('painel'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar permuta: {str(e)}', 'danger')
        return redirect(url_for('painel')))
@app.route('/assinar_substituto/<int:permuta_id>')
@login_required
def assinar_substituto(permuta_id):
    p = db.session.get(Permuta, permuta_id)
    if p and p.substituto_id == current_user.id and p.status == 'Aguardando Substituto':
        p.status = 'Pendente'
        db.session.commit()
        flash('Permuta assinada com sucesso pelo substituto! Encaminhada para análise do Escalante.', 'success')
    return redirect(url_for('painel'))

@app.route('/recusar_substituto/<int:permuta_id>')
@login_required
def recusar_substituto(permuta_id):
    p = db.session.get(Permuta, permuta_id)
    if p and p.substituto_id == current_user.id and p.status == 'Aguardando Substituto':
        p.status = 'Recusada pelo Substituto'
        db.session.commit()
        flash('Você recusou esta solicitação de permuta.', 'warning')
    return redirect(url_for('painel'))
@app.route('/autorizar_permuta/<int:permuta_id>')
@login_required
def autorizar_permuta(permuta_id):
    if current_user.is_admin:
        p = db.session.get(Permuta, permuta_id)
        if p:
            p.status = 'Autorizada'
            db.session.commit()
            flash('Permuta autorizada com sucesso!', 'success')
    return redirect(url_for('painel'))

@app.route('/rejeitar_permuta/<int:permuta_id>')
@login_required
def rejeitar_permuta(permuta_id):
    if current_user.is_admin:
        p = db.session.get(Permuta, permuta_id)
        if p:
            p.status = 'Rejeitada'
            db.session.commit()
            flash('Permuta rejeitada.', 'warning')
    return redirect(url_for('painel'))
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
