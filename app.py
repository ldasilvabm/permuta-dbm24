from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui'

# Configuração segura do banco de dados SQLite com caminho absoluto
import os

# Usa a pasta /tmp no Render para garantir permissão total de escrita do SQLite
if 'RENDER' in os.environ:
    db_path = '/tmp/database.db'
else:
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(basedir, 'database.db')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Cria o banco de dados limpo utilizando o caminho seguro correto
with app.app_context():
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except:
            pass
    db.create_all()

# Modelo de Usuário (Militar)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    graduacao = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_approved = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rota de Login
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

# Rota de Registro
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        graduacao = request.form.get('graduacao')
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

# Painel Principal
@app.route('/painel')
@login_required
def painel():
    usuarios_pendentes = []
    todos_usuarios = []
    if current_user.is_admin:
        usuarios_pendentes = User.query.filter_by(is_approved=False).all()
        todos_usuarios = User.query.all()
    return render_template('painel.html', usuarios_pendentes=usuarios_pendentes, todos_usuarios=todos_usuarios)

# Aprovar Cadastro
@app.route('/aprovar/<int:user_id>')
@login_required
def aprovar(user_id):
    if current_user.is_admin:
        user = User.query.get(user_id)
        if user:
            user.is_approved = True
            db.session.commit()
            flash(f'Cadastro de {user.nome} aprovado!', 'success')
    return redirect(url_for('painel'))

# Promover ou Remover Escalante
@app.route('/toggle_admin/<int:user_id>')
@login_required
def toggle_admin(user_id):
    if current_user.is_admin:
        user = User.query.get(user_id)
        if user and user.id != current_user.id:
            user.is_admin = not user.is_admin
            db.session.commit()
            flash(f'Permissões de Escalante atualizadas para {user.nome}.', 'success')
    return redirect(url_for('painel'))

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
