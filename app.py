from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///quiz_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    coins = db.Column(db.Integer, default=100)
    profile_theme = db.Column(db.String(50), default='dark')
    avatar_frame = db.Column(db.String(50), default='none')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_daily_bonus = db.Column(db.DateTime, default=None)


class Card(db.Model):
    __tablename__ = 'card'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    rarity = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200))
    base_price = db.Column(db.Integer, default=50)


class UserCard(db.Model):
    __tablename__ = 'user_card'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    level = db.Column(db.Integer, default=1)

    user = db.relationship('User', backref=db.backref('cards', lazy=True))
    card = db.relationship('Card', backref=db.backref('user_cards', lazy=True))


class Quiz(db.Model):
    __tablename__ = 'quiz'

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    reward_coins = db.Column(db.Integer, default=50)
    passing_score = db.Column(db.Integer, default=60)


class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option1 = db.Column(db.String(200), nullable=False)
    option2 = db.Column(db.String(200), nullable=False)
    option3 = db.Column(db.String(200), nullable=False)
    option4 = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.Integer, nullable=False)

    quiz = db.relationship('Quiz', backref=db.backref('questions', lazy=True))


class QuizResult(db.Model):
    __tablename__ = 'quiz_result'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)


class ShopItem(db.Model):
    __tablename__ = 'shop_item'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    pack_rarity_chances = db.Column(db.String(200))


class TradeOffer(db.Model):
    __tablename__ = 'trade_offer'

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    offered_card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    requested_card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='sent_trade_offers')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='received_trade_offers')
    offered_card = db.relationship('Card', foreign_keys=[offered_card_id])
    requested_card = db.relationship('Card', foreign_keys=[requested_card_id])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def add_card_to_user(user_id, card_id, quantity=1):
    user_card = UserCard.query.filter_by(user_id=user_id, card_id=card_id).first()
    if user_card:
        user_card.quantity += quantity
    else:
        db.session.add(UserCard(user_id=user_id, card_id=card_id, quantity=quantity))


def remove_card_from_user(user_id, card_id, quantity=1):
    user_card = UserCard.query.filter_by(user_id=user_id, card_id=card_id).first()
    if not user_card or user_card.quantity < quantity:
        return False

    user_card.quantity -= quantity
    if user_card.quantity <= 0:
        db.session.delete(user_card)
    return True


def seed_data():
    if not Card.query.first():
        cards = [
            Card(name='Иванов И.И.', description='Преподаватель математики', rarity='common', subject='Математика', base_price=50),
            Card(name='Петров П.П.', description='Преподаватель программирования', rarity='rare', subject='Программирование', base_price=80),
            Card(name='Сидорова А.А.', description='Преподаватель физики', rarity='epic', subject='Физика', base_price=120),
            Card(name='Кузнецов К.К.', description='Легендарный преподаватель ИИ', rarity='legendary', subject='ИИ', base_price=250),
        ]
        db.session.add_all(cards)

    if not Quiz.query.first():
        quiz1 = Quiz(subject='Математика', title='Базовый тест по математике', reward_coins=30, passing_score=60)
        quiz2 = Quiz(subject='Программирование', title='Основы Python', reward_coins=40, passing_score=60)
        db.session.add_all([quiz1, quiz2])
        db.session.flush()

        questions = [
            Question(quiz_id=quiz1.id, text='Сколько будет 2 + 2?', option1='3', option2='4', option3='5', option4='6', correct_option=2),
            Question(quiz_id=quiz1.id, text='Сколько градусов в прямом угле?', option1='45', option2='90', option3='120', option4='180', correct_option=2),
            Question(quiz_id=quiz2.id, text='Какой тип у 10 в Python?', option1='str', option2='float', option3='int', option4='bool', correct_option=3),
            Question(quiz_id=quiz2.id, text='Какой оператор используется для цикла?', option1='if', option2='for', option3='def', option4='class', correct_option=2),
        ]
        db.session.add_all(questions)

    if not ShopItem.query.first():
        shop_items = [
            ShopItem(name='Неоновая тема', type='theme', price=0, description='Тёмная тема с зелёно-фиолетовыми акцентами'),
            ShopItem(name='Светлая тема', type='theme', price=0, description='Светлая тема с белыми, зелёными и фиолетовыми акцентами'),
            ShopItem(name='Фиолетовая рамка', type='frame', price=80, description='Яркая рамка для аватара'),
            ShopItem(name='Пакет карточек', type='card_pack', price=100, description='Случайная коллекционная карточка'),
        ]
        db.session.add_all(shop_items)

    card_pack = ShopItem.query.filter_by(type='card_pack').first()
    if card_pack:
        card_pack.price = 100
        card_pack.description = 'Случайная коллекционная карточка'

    db.session.commit()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('Заполните все поля')
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован')
            return redirect(url_for('register'))

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна! Теперь войдите в аккаунт.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('profile'))

        flash('Неверное имя пользователя или пароль')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)


@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('profile.html', user=user)


@app.route('/collection')
@login_required
def collection():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    return render_template('collection.html', user_cards=user_cards)


@app.route('/toggle_theme')
@login_required
def toggle_theme():
    current_user.profile_theme = 'light' if current_user.profile_theme == 'dark' else 'dark'
    db.session.commit()
    flash('Тема оформления обновлена')
    return redirect(request.referrer or url_for('profile'))


RARITY_SELL_PRICES = {
    'common': 25,
    'rare': 50,
    'epic': 75,
    'legendary': 90,
}


@app.route('/sell_card/<int:card_id>', methods=['POST'])
@login_required
def sell_card(card_id):
    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card_id).first_or_404()

    if user_card.quantity <= 1:
        flash('Продавать можно только дубликаты карточек')
        return redirect(url_for('collection'))

    sell_price = RARITY_SELL_PRICES.get(user_card.card.rarity, 25)
    user_card.quantity -= 1
    current_user.coins += sell_price
    db.session.commit()

    flash(f'Карточка продана за {sell_price} монет')
    return redirect(url_for('collection'))


@app.route('/quizzes')
@login_required
def quizzes():
    quizzes_list = Quiz.query.all()
    return render_template('quizzes.html', quizzes=quizzes_list)


@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
@login_required
def take_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz_id).all()

    if request.method == 'POST':
        correct = 0
        total = len(questions)

        for question in questions:
            answer = request.form.get(f'question_{question.id}')
            if answer and int(answer) == question.correct_option:
                correct += 1

        score = int((correct / total) * 100) if total > 0 else 0
        passed = score >= quiz.passing_score

        result = QuizResult(
            user_id=current_user.id,
            quiz_id=quiz_id,
            score=score,
            passed=passed
        )
        db.session.add(result)

        if passed:
            current_user.coins += quiz.reward_coins
            flash(f'Тест пройден! +{quiz.reward_coins} монет')
        else:
            flash(f'Тест не пройден. Набрано {score}%')

        db.session.commit()
        return redirect(url_for('quizzes'))

    return render_template('quiz.html', quiz=quiz, questions=questions)


@app.route('/shop')
@login_required
def shop():
    frames = ShopItem.query.filter_by(type='frame').all()
    card_pack = ShopItem.query.filter_by(type='card_pack').first()
    return render_template('shop.html', frames=frames, card_pack=card_pack)


@app.route('/buy_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def buy_item(item_id):
    item = ShopItem.query.get_or_404(item_id)

    if current_user.coins < item.price:
        flash('Недостаточно монет')
        return redirect(url_for('shop'))

    current_user.coins -= item.price

    if item.type == 'theme':
        flash('Темы теперь бесплатные и переключаются кнопкой в углу экрана')
    elif item.type == 'frame':
        current_user.avatar_frame = 'neon-frame'
        flash(f'Вы купили рамку: {item.name}')
    elif item.type == 'card_pack':
        cards = Card.query.all()
        if cards:
            weights = []
            for card in cards:
                if card.rarity == 'common':
                    weights.append(60)
                elif card.rarity == 'rare':
                    weights.append(25)
                elif card.rarity == 'epic':
                    weights.append(10)
                else:
                    weights.append(5)
            card = random.choices(cards, weights=weights, k=1)[0]
            add_card_to_user(current_user.id, card.id)
            db.session.commit()
            session['last_pack_result'] = card.id
            return redirect(url_for('pack_result'))

    db.session.commit()
    return redirect(url_for('shop'))




@app.route('/pack-result')
@login_required
def pack_result():
    card_id = session.pop('last_pack_result', None)
    if not card_id:
        flash('Сначала откройте пакет в магазине')
        return redirect(url_for('shop'))

    card = Card.query.get_or_404(card_id)
    duplicate_count = UserCard.query.filter_by(user_id=current_user.id, card_id=card.id).first()
    return render_template('pack_result.html', card=card, duplicate_count=duplicate_count.quantity if duplicate_count else 1)


@app.route('/exchange', methods=['GET', 'POST'])
@login_required
def exchange():
    if request.method == 'POST':
        to_user_id = request.form.get('to_user_id', type=int)
        offered_card_id = request.form.get('offered_card_id', type=int)
        requested_card_id = request.form.get('requested_card_id', type=int)

        if not to_user_id or not offered_card_id or not requested_card_id:
            flash('Заполните все поля обмена')
            return redirect(url_for('exchange'))

        if to_user_id == current_user.id:
            flash('Нельзя отправить обмен самому себе')
            return redirect(url_for('exchange'))

        own_card = UserCard.query.filter_by(user_id=current_user.id, card_id=offered_card_id).first()
        target_card = UserCard.query.filter_by(user_id=to_user_id, card_id=requested_card_id).first()

        if not own_card or own_card.quantity < 1:
            flash('У вас нет выбранной карточки для обмена')
            return redirect(url_for('exchange'))

        if not target_card or target_card.quantity < 1:
            flash('У выбранного пользователя нет запрошенной карточки')
            return redirect(url_for('exchange'))

        offer = TradeOffer(
            from_user_id=current_user.id,
            to_user_id=to_user_id,
            offered_card_id=offered_card_id,
            requested_card_id=requested_card_id,
            status='pending'
        )
        db.session.add(offer)
        db.session.commit()
        flash('Предложение обмена отправлено')
        return redirect(url_for('exchange'))

    users = User.query.filter(User.id != current_user.id).all()
    my_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    incoming_offers = TradeOffer.query.filter_by(to_user_id=current_user.id, status='pending').order_by(TradeOffer.created_at.desc()).all()
    outgoing_offers = TradeOffer.query.filter_by(from_user_id=current_user.id).order_by(TradeOffer.created_at.desc()).all()
    return render_template('exchange.html', users=users, my_cards=my_cards, incoming_offers=incoming_offers, outgoing_offers=outgoing_offers)


@app.route('/exchange/accept/<int:offer_id>', methods=['POST'])
@login_required
def accept_exchange(offer_id):
    offer = TradeOffer.query.get_or_404(offer_id)

    if offer.to_user_id != current_user.id or offer.status != 'pending':
        flash('Обмен недоступен')
        return redirect(url_for('exchange'))

    sender_card = UserCard.query.filter_by(user_id=offer.from_user_id, card_id=offer.offered_card_id).first()
    receiver_card = UserCard.query.filter_by(user_id=offer.to_user_id, card_id=offer.requested_card_id).first()

    if not sender_card or sender_card.quantity < 1:
        offer.status = 'cancelled'
        db.session.commit()
        flash('У отправителя больше нет карточки для обмена')
        return redirect(url_for('exchange'))

    if not receiver_card or receiver_card.quantity < 1:
        offer.status = 'cancelled'
        db.session.commit()
        flash('У вас больше нет карточки для обмена')
        return redirect(url_for('exchange'))

    remove_card_from_user(offer.from_user_id, offer.offered_card_id)
    remove_card_from_user(offer.to_user_id, offer.requested_card_id)
    add_card_to_user(offer.from_user_id, offer.requested_card_id)
    add_card_to_user(offer.to_user_id, offer.offered_card_id)

    offer.status = 'accepted'
    db.session.commit()
    flash('Обмен успешно выполнен')
    return redirect(url_for('exchange'))


@app.route('/exchange/reject/<int:offer_id>', methods=['POST'])
@login_required
def reject_exchange(offer_id):
    offer = TradeOffer.query.get_or_404(offer_id)
    if offer.to_user_id != current_user.id or offer.status != 'pending':
        flash('Обмен недоступен')
        return redirect(url_for('exchange'))

    offer.status = 'rejected'
    db.session.commit()
    flash('Предложение отклонено')
    return redirect(url_for('exchange'))


@app.route('/rating')
@login_required
def rating():
    users = User.query.all()
    enriched = []
    for user in users:
        cards_value = sum((uc.card.base_price or 0) * uc.quantity for uc in user.cards)
        enriched.append((user, user.coins + cards_value))
    enriched.sort(key=lambda item: item[1], reverse=True)
    return render_template('rating.html', users=enriched)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_data()
    app.run(debug=True)
