from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from datetime import datetime
import random
import json
import os
import re
import shutil
from pathlib import Path


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(BASE_DIR, 'instance', 'quiz_platform.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {'timeout': 20, 'check_same_thread': False}
}
os.makedirs(app.instance_path, exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

RARITY_SELL_PRICES = {
    'common': 25,
    'rare': 50,
    'epic': 75,
    'legendary': 90,
}

STAR_UPGRADE_COSTS = [3, 6, 9, 15, 30, 60, 100]
STAR_WEALTH_MULTIPLIER = [1.0, 1.25, 1.55, 1.9, 2.3, 2.8, 3.4, 4.1]


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    coins = db.Column(db.Integer, default=100)
    profile_theme = db.Column(db.String(50), default='dark')
    avatar_frame = db.Column(db.String(50), default='none')
    bio = db.Column(db.Text, default='')
    owned_frames = db.Column(db.Text, default='[]')
    avatar_icon = db.Column(db.String(50), default='letter')
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
    star_level = db.Column(db.Integer, default=0)

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




class TradeRequest(db.Model):
    __tablename__ = 'trade_request'

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship('User', foreign_keys=[requester_id], backref='trade_requests')
    target_user = db.relationship('User', foreign_keys=[target_user_id])
    requested_card = db.relationship('Card', foreign_keys=[requested_card_id])


class WishlistItem(db.Model):
    __tablename__ = 'wishlist_item'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('wishlist_items', lazy=True, cascade='all, delete-orphan'))
    card = db.relationship('Card', backref=db.backref('wishlist_entries', lazy=True, cascade='all, delete-orphan'))


class Friendship(db.Model):
    __tablename__ = 'friendship'

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    addressee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship('User', foreign_keys=[requester_id], backref=db.backref('sent_friend_requests', lazy=True, cascade='all, delete-orphan'))
    addressee = db.relationship('User', foreign_keys=[addressee_id], backref=db.backref('received_friend_requests', lazy=True, cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('requester_id', 'addressee_id', name='uq_friendship_pair'),
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ensure_database_schema():
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if 'user' in table_names:
        user_columns = {column['name'] for column in inspector.get_columns('user')}
        if 'bio' not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN bio TEXT DEFAULT ''"))
        if 'owned_frames' not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN owned_frames TEXT DEFAULT '[]'"))
        if 'avatar_icon' not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN avatar_icon TEXT DEFAULT 'letter'"))
        if 'last_daily_bonus' not in user_columns:
            db.session.execute(text("ALTER TABLE user ADD COLUMN last_daily_bonus DATETIME DEFAULT NULL"))
        db.session.commit()
        db.session.execute(text("UPDATE user SET bio = '' WHERE bio IS NULL"))
        db.session.execute(text("UPDATE user SET owned_frames = '[]' WHERE owned_frames IS NULL OR owned_frames = ''"))
        db.session.execute(text("UPDATE user SET avatar_icon = 'letter' WHERE avatar_icon IS NULL OR avatar_icon = ''"))
        db.session.commit()

    if 'user_card' in table_names:
        user_card_columns = {column['name'] for column in inspector.get_columns('user_card')}
        if 'star_level' not in user_card_columns:
            db.session.execute(text("ALTER TABLE user_card ADD COLUMN star_level INTEGER DEFAULT 0"))
            db.session.commit()
        db.session.execute(text("UPDATE user_card SET star_level = 0 WHERE star_level IS NULL"))
        db.session.commit()


def get_owned_frame_codes(user):
    try:
        frames = json.loads(user.owned_frames or '[]')
        return frames if isinstance(frames, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def save_owned_frame_codes(user, frame_codes):
    unique_codes = []
    for frame_code in frame_codes:
        if frame_code and frame_code not in unique_codes:
            unique_codes.append(frame_code)
    user.owned_frames = json.dumps(unique_codes, ensure_ascii=False)


def get_frame_code(item):
    image_value = item.image_url or ''
    if image_value.startswith('frames/'):
        return Path(image_value).stem
    return image_value or f'frame-{item.id}'


def prettify_frame_name(stem):
    raw = stem.replace('_', ' ').replace('-', ' ')
    words = [word for word in raw.split() if word.lower() != 'frame']
    title = ' '.join(word.capitalize() for word in words) or 'Рамка'
    return f"{title} рамка"


def sync_frame_assets():
    root = Path(app.root_path)
    source_dirs = [root / 'Frames', root / 'frames']
    static_dir = root / 'static' / 'frames'
    static_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for source_dir in source_dirs:
        if not source_dir.exists():
            continue
        for file in source_dir.iterdir():
            if file.suffix.lower() not in {'.png', '.webp', '.jpg', '.jpeg'}:
                continue
            target = static_dir / file.name
            if not target.exists() or file.stat().st_mtime > target.stat().st_mtime:
                shutil.copy2(file, target)
            copied.append(target)
    return copied


def get_frame_asset_url(frame_or_code):
    code = frame_or_code
    if not isinstance(frame_or_code, str):
        code = get_frame_code(frame_or_code)
    root = Path(app.root_path) / 'static' / 'frames'
    if not root.exists():
        return None
    for file in root.iterdir():
        if file.is_file() and file.stem.lower() == str(code).lower():
            return url_for('static', filename=f'frames/{file.name}')
    return None


def add_frame_to_user(user, item):
    frame_code = get_frame_code(item)
    owned_frames = get_owned_frame_codes(user)
    if frame_code in owned_frames:
        return False
    owned_frames.append(frame_code)
    save_owned_frame_codes(user, owned_frames)
    return True


def get_available_frames_for_user(user):
    owned_codes = set(get_owned_frame_codes(user))
    if not owned_codes:
        return []
    all_frames = ShopItem.query.filter_by(type='frame').all()
    return [frame for frame in all_frames if get_frame_code(frame) in owned_codes]


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


def get_card_letter(card):
    return {
        'common': 'C',
        'rare': 'R',
        'epic': 'E',
        'legendary': 'L',
    }.get(card.rarity, '?')


def get_avatar_icons():
    return [
        {'code': 'letter', 'symbol': None, 'label': 'Буква имени'},
        {'code': 'rocket', 'symbol': '🚀', 'label': 'Ракета'},
        {'code': 'crown', 'symbol': '👑', 'label': 'Корона'},
        {'code': 'ghost', 'symbol': '👾', 'label': 'Пиксельный герой'},
        {'code': 'robot', 'symbol': '🤖', 'label': 'Робот'},
        {'code': 'fox', 'symbol': '🦊', 'label': 'Лис'},
        {'code': 'dragon', 'symbol': '🐉', 'label': 'Дракон'},
        {'code': 'wizard', 'symbol': '🧙', 'label': 'Маг'},
    ]


def get_avatar_icon_symbol(user):
    icon_map = {item['code']: item['symbol'] for item in get_avatar_icons()}
    return icon_map.get(getattr(user, 'avatar_icon', 'letter'))


def get_star_upgrade_cost(current_star_level):
    if current_star_level < 0 or current_star_level >= len(STAR_UPGRADE_COSTS):
        return None
    return STAR_UPGRADE_COSTS[current_star_level]


def get_star_multiplier(star_level):
    star_level = max(0, min(int(star_level or 0), len(STAR_WEALTH_MULTIPLIER) - 1))
    return STAR_WEALTH_MULTIPLIER[star_level]


def get_card_stars_display(star_level):
    star_level = max(0, int(star_level or 0))
    return '★' * star_level + '☆' * (7 - star_level)


def get_user_card_wealth(user_card):
    base_price = user_card.card.base_price or 0
    quantity_value = base_price * (user_card.quantity or 0)
    upgrade_bonus = int(base_price * (get_star_multiplier(user_card.star_level) - 1))
    return quantity_value + upgrade_bonus


def is_card_in_wishlist(user_id, card_id):
    return WishlistItem.query.filter_by(user_id=user_id, card_id=card_id).first() is not None


DAILY_BONUS_AMOUNT = 100


def can_claim_daily_bonus(user):
    last_bonus = getattr(user, 'last_daily_bonus', None)
    return not last_bonus or last_bonus.date() < datetime.utcnow().date()


def get_friendship_between(user_one_id, user_two_id):
    return Friendship.query.filter(
        db.or_(
            db.and_(Friendship.requester_id == user_one_id, Friendship.addressee_id == user_two_id),
            db.and_(Friendship.requester_id == user_two_id, Friendship.addressee_id == user_one_id),
        )
    ).first()


def get_user_friends(user_id):
    accepted = Friendship.query.filter(
        Friendship.status == 'accepted',
        db.or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
    ).order_by(Friendship.created_at.desc()).all()
    friends = []
    for friendship in accepted:
        friends.append(friendship.addressee if friendship.requester_id == user_id else friendship.requester)
    return friends




def get_card_owners(card_id, exclude_user_id=None):
    query = UserCard.query.filter_by(card_id=card_id).filter(UserCard.quantity >= 1)
    if exclude_user_id is not None:
        query = query.filter(UserCard.user_id != exclude_user_id)
    return query.order_by(UserCard.quantity.desc(), UserCard.user_id.asc()).all()


def get_frame_collection(frame_or_code):
    code = frame_or_code if isinstance(frame_or_code, str) else get_frame_code(frame_or_code)
    normalized = str(code).lower()
    return 'fire' if 'fire' in normalized else 'gems'


def get_frame_pack_meta(pack_code):
    packs = {
        'gems-frame-pack': {
            'collection': 'gems',
            'label': 'Gems',
            'icon': '💎',
            'accent': 'gems',
            'description': 'Рулетка с кристальными рамками для профиля.',
        },
        'fire-frame-pack': {
            'collection': 'fire',
            'label': 'Fire',
            'icon': '🔥',
            'accent': 'fire',
            'description': 'Рулетка с огненными рамками для профиля.',
        },
    }
    return packs.get(pack_code, packs['gems-frame-pack'])

def seed_data():
    sync_frame_assets()
    
    if not Card.query.first():
        cards = [
            Card(name='Вход', description='приключение на 4 года', rarity='common', subject='Вуз', base_price=50, image_url='/static/img/cards/enter.jpg'),
            Card(name='Унифуд', description='Хоть где-то реаьно круто', rarity='rare', subject='Вуз', base_price=85, image_url='/static/img/cards/cafe.jpg'),
            Card(name='ДАААВИИИИД', description='Сильнейший человек на планете, жаль что ещё не все его знают', rarity='epic', subject='ИКБО-30-23', base_price=130, image_url='/static/img/cards/david.jpg'),
            Card(name='Шошников', description='Безумно любит нас и работу', rarity='legendary', subject='Захват Движения', base_price=250, image_url='/static/img/cards/shosh.jpg'),
            Card(name='Дзержинский', description='Легендарный преподаватель, самый лучший', rarity='legendary', subject='Математика', base_price=250, image_url='/static/img/cards/Dzerj.jpg'),
            Card(name='Шутов', description='Лучший геймдизайнер', rarity='legendary', subject='Геймдизайн', base_price=250, image_url='/static/img/cards/Shutov.jpg'),
            Card(name='Иерусалимов', description='Преподаватель, спасший группу', rarity='legendary', subject='Геймдизайн', base_price=250, image_url='/static/img/cards/Ierusalimov.jpg'),
            Card(name='Карпов', description='Самый весёлый преподаватель', rarity='legendary', subject='Информатика', base_price=250, image_url='/static/img/cards/karpov.jpg'),
            Card(name='Акатьев', description='Великий человек', rarity='legendary', subject='Глава', base_price=250, image_url='/static/img/cards/main.jpg'),
            Card(name='Воронцова', description='Дай бог здоровья таким людям', rarity='epic', subject='МОСИТ', base_price=130, image_url='/static/img/cards/woman.jpg'),
            Card(name='Воронцов', description='Дай бог счастья таким людям', rarity='epic', subject='МОСИТ', base_price=130, image_url='/static/img/cards/man.jpg'),
            Card(name='Воронцовы', description='Дай бог любви таким людям', rarity='legendary', subject='МОСИТ', base_price=250, image_url='/static/img/cards/pair.jpg'),
        ]
        db.session.add_all(cards)
        print("✅ Карточки с картинками добавлены в базу")

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

    defaults = [
        ('teacher-pack', 'Рулетка карточек преподавателей', 'card_pack', 100, 'Открывайте карточки преподавателей с анимацией 1 / 3 / 5 за раз.'),
        ('gems-frame-pack', 'Рулетка рамочек Gems', 'frame_pack', 120, 'Крутите кристальные рамки для профиля с компенсацией за дубликаты.'),
        ('fire-frame-pack', 'Рулетка рамочек Fire', 'frame_pack', 145, 'Крутите огненные рамки для профиля с компенсацией за дубликаты.'),
    ]

    for code, name, item_type, price, description in defaults:
        item = ShopItem.query.filter_by(image_url=code).first()
        if not item:
            item = ShopItem(name=name, type=item_type, price=price, description=description, image_url=code)
            db.session.add(item)
        else:
            item.name = name
            item.type = item_type
            item.price = price
            item.description = description

    static_frames_dir = Path(app.root_path) / 'static' / 'frames'
    dynamic_prices = {
        'amethyst_frame': 80,
        'emerald_frame': 95,
        'diamond_frame': 110,
        'citrin_frame': 115,
        'ruby_frame': 125,
        'bluefire_frame': 135,
        'limefire_frame': 140,
        'pinkfire_frame': 145,
        'redfire_frame': 150,
    }
    if static_frames_dir.exists():
        for file in static_frames_dir.iterdir():
            if file.suffix.lower() not in {'.png', '.webp', '.jpg', '.jpeg'}:
                continue
            code = file.stem
            item = ShopItem.query.filter_by(image_url=code).first()
            price = dynamic_prices.get(code.lower(), 100)
            if not item:
                db.session.add(ShopItem(
                    name=prettify_frame_name(code),
                    type='frame',
                    price=price,
                    description='Коллекционная рамка для профиля из набора Frames.',
                    image_url=code
                ))
            else:
                item.type = 'frame'
                item.price = price
                if not item.description:
                    item.description = 'Коллекционная рамка для профиля из набора Frames.'

    db.session.commit()
    print("✅ Карточки с картинками добавлены в базу")


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
            password_hash=generate_password_hash(password),
            bio='',
            owned_frames='[]',
            avatar_icon='letter'
        )
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('База данных временно занята. Перезапустите приложение и попробуйте снова.')
            return redirect(url_for('register'))

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




@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip()
        new_password = request.form.get('new_password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if not username or not email or not new_password or not confirm_password:
            flash('Заполните все поля')
            return redirect(url_for('reset_password'))

        if new_password != confirm_password:
            flash('Пароли не совпадают')
            return redirect(url_for('reset_password'))

        if len(new_password) < 4:
            flash('Пароль должен содержать минимум 4 символа')
            return redirect(url_for('reset_password'))

        user = User.query.filter_by(username=username, email=email).first()
        if not user:
            flash('Пользователь с таким именем и email не найден')
            return redirect(url_for('reset_password'))

        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Пароль обновлён. Теперь можно войти с новым паролем.')
        return redirect(url_for('login'))

    return render_template('reset_password.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            current_user.bio = (request.form.get('bio') or '').strip()[:400]
            db.session.commit()
            flash('Описание профиля обновлено')
            return redirect(url_for('profile'))

        if action == 'set_frame':
            selected_frame = request.form.get('avatar_frame', 'none')
            available_codes = {get_frame_code(frame) for frame in get_available_frames_for_user(current_user)}
            if selected_frame == 'none' or selected_frame in available_codes:
                current_user.avatar_frame = selected_frame
                db.session.commit()
                flash('Рамка профиля обновлена')
            else:
                flash('Эта рамка недоступна для вашего аккаунта')
            return redirect(url_for('profile'))

        if action == 'set_icon':
            selected_icon = request.form.get('avatar_icon', 'letter')
            available_icon_codes = {item['code'] for item in get_avatar_icons()}
            if selected_icon in available_icon_codes:
                current_user.avatar_icon = selected_icon
                db.session.commit()
                flash('Иконка профиля обновлена')
            else:
                flash('Эта иконка недоступна')
            return redirect(url_for('profile'))

    owned_frames = get_available_frames_for_user(current_user)
    wishlist_ids = {item.card_id for item in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    return render_template(
        'profile.html',
        user=current_user,
        owned_frames=owned_frames,
        is_owner=True,
        wishlist_ids=wishlist_ids,
        viewed_wishlist_cards=[],
        get_card_letter=get_card_letter,
        avatar_icons=get_avatar_icons(),
        get_avatar_icon_symbol=get_avatar_icon_symbol,
        get_card_stars_display=get_card_stars_display,
        can_claim_daily_bonus=can_claim_daily_bonus(current_user),
        daily_bonus_amount=DAILY_BONUS_AMOUNT,
        friends=get_user_friends(current_user.id),
        friendship_status=None,
    )


@app.route('/profile/<int:user_id>')
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    owned_frames = get_available_frames_for_user(user)
    wishlist_ids = {item.card_id for item in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    viewed_wishlist_cards = (
        db.session.query(Card)
        .join(WishlistItem, WishlistItem.card_id == Card.id)
        .filter(WishlistItem.user_id == user.id)
        .order_by(WishlistItem.created_at.desc(), Card.name.asc())
        .all()
    )
    friendship = None if user.id == current_user.id else get_friendship_between(current_user.id, user.id)
    return render_template(
        'profile.html',
        user=user,
        owned_frames=owned_frames,
        is_owner=user.id == current_user.id,
        wishlist_ids=wishlist_ids,
        viewed_wishlist_cards=viewed_wishlist_cards,
        get_card_letter=get_card_letter,
        avatar_icons=get_avatar_icons(),
        get_avatar_icon_symbol=get_avatar_icon_symbol,
        get_card_stars_display=get_card_stars_display,
        can_claim_daily_bonus=False,
        daily_bonus_amount=DAILY_BONUS_AMOUNT,
        friends=get_user_friends(user.id),
        friendship_status=friendship,
    )


@app.route('/daily-bonus', methods=['POST'])
@login_required
def claim_daily_bonus():
    if not can_claim_daily_bonus(current_user):
        flash('Ежедневная награда уже получена. Возвращайтесь завтра!')
        return redirect(request.referrer or url_for('profile'))

    current_user.coins += DAILY_BONUS_AMOUNT
    current_user.last_daily_bonus = datetime.utcnow()
    db.session.commit()
    flash(f'Вы получили ежедневную награду: +{DAILY_BONUS_AMOUNT} монет')
    return redirect(request.referrer or url_for('profile'))


@app.route('/friends', methods=['GET', 'POST'])
@login_required
def friends():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        target = User.query.filter(db.func.lower(User.username) == username.lower()).first() if username else None

        if not target:
            flash('Пользователь не найден')
        elif target.id == current_user.id:
            flash('Нельзя добавить самого себя')
        else:
            existing = get_friendship_between(current_user.id, target.id)
            if existing:
                if existing.status == 'accepted':
                    flash('Вы уже друзья')
                elif existing.requester_id == current_user.id:
                    flash('Заявка уже отправлена')
                else:
                    existing.status = 'accepted'
                    db.session.commit()
                    flash(f'Вы приняли заявку от {target.username}')
            else:
                db.session.add(Friendship(requester_id=current_user.id, addressee_id=target.id))
                db.session.commit()
                flash(f'Заявка в друзья отправлена пользователю {target.username}')
        return redirect(url_for('friends'))

    incoming_requests = Friendship.query.filter_by(addressee_id=current_user.id, status='pending').order_by(Friendship.created_at.desc()).all()
    outgoing_requests = Friendship.query.filter_by(requester_id=current_user.id, status='pending').order_by(Friendship.created_at.desc()).all()
    return render_template(
        'friends.html',
        friends=get_user_friends(current_user.id),
        incoming_requests=incoming_requests,
        outgoing_requests=outgoing_requests,
    )


@app.route('/friends/<int:friendship_id>/<action>', methods=['POST'])
@login_required
def update_friendship(friendship_id, action):
    friendship = Friendship.query.get_or_404(friendship_id)

    if action == 'accept' and friendship.addressee_id == current_user.id and friendship.status == 'pending':
        friendship.status = 'accepted'
        db.session.commit()
        flash('Заявка принята')
    elif action in {'reject', 'remove'} and current_user.id in {friendship.requester_id, friendship.addressee_id}:
        db.session.delete(friendship)
        db.session.commit()
        flash('Запись о дружбе удалена')
    else:
        flash('Действие недоступно')

    return redirect(request.referrer or url_for('friends'))


@app.route('/friends/add/<int:user_id>', methods=['POST'])
@login_required
def add_friend_from_profile(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        flash('Нельзя добавить самого себя')
        return redirect(url_for('profile'))

    existing = get_friendship_between(current_user.id, target.id)
    if existing:
        if existing.status == 'accepted':
            flash('Вы уже друзья')
        elif existing.requester_id == current_user.id:
            flash('Заявка уже отправлена')
        else:
            existing.status = 'accepted'
            db.session.commit()
            flash(f'Вы приняли заявку от {target.username}')
    else:
        db.session.add(Friendship(requester_id=current_user.id, addressee_id=target.id))
        db.session.commit()
        flash(f'Заявка в друзья отправлена пользователю {target.username}')

    return redirect(url_for('view_profile', user_id=target.id))


@app.route('/collection')
@login_required
def collection():
    user_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    wishlist_ids = {item.card_id for item in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    return render_template('collection.html', user_cards=user_cards, wishlist_ids=wishlist_ids, get_card_letter=get_card_letter, get_star_upgrade_cost=get_star_upgrade_cost, get_card_stars_display=get_card_stars_display)


@app.route('/cards')
@login_required
def cards_catalog():
    cards = Card.query.order_by(Card.rarity.desc(), Card.name.asc()).all()
    wishlist_ids = {item.card_id for item in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    owned_ids = {item.card_id for item in UserCard.query.filter_by(user_id=current_user.id).all()}
    return render_template('cards.html', cards=cards, wishlist_ids=wishlist_ids, owned_ids=owned_ids, get_card_letter=get_card_letter, get_card_stars_display=get_card_stars_display)


@app.route('/wishlist')
@login_required
def wishlist():
    entries = WishlistItem.query.filter_by(user_id=current_user.id).order_by(WishlistItem.created_at.desc()).all()
    cards = [entry.card for entry in entries]
    owned_ids = {item.card_id for item in UserCard.query.filter_by(user_id=current_user.id).all()}
    wishlist_ids = {entry.card_id for entry in entries}
    return render_template('wishlist.html', cards=cards, owned_ids=owned_ids, wishlist_ids=wishlist_ids, get_card_letter=get_card_letter, get_card_stars_display=get_card_stars_display)


@app.route('/wishlist/toggle/<int:card_id>', methods=['POST'])
@login_required
def toggle_wishlist(card_id):
    card = Card.query.get_or_404(card_id)
    existing = WishlistItem.query.filter_by(user_id=current_user.id, card_id=card.id).first()
    if existing:
        db.session.delete(existing)
        flash(f'Карточка «{card.name}» убрана из списка желаемого')
    else:
        db.session.add(WishlistItem(user_id=current_user.id, card_id=card.id))
        flash(f'Карточка «{card.name}» добавлена в список желаемого')
    db.session.commit()
    return redirect(request.referrer or url_for('cards_catalog'))




@app.route('/card/<int:card_id>/owners')
@login_required
def card_owners(card_id):
    card = Card.query.get_or_404(card_id)
    owners = get_card_owners(card.id, exclude_user_id=current_user.id)
    wishlist_ids = {item.card_id for item in WishlistItem.query.filter_by(user_id=current_user.id).all()}
    return render_template('card_owners.html', card=card, owners=owners, wishlist_ids=wishlist_ids, get_card_letter=get_card_letter, get_card_stars_display=get_card_stars_display)

@app.route('/toggle_theme')
@login_required
def toggle_theme():
    current_user.profile_theme = 'light' if current_user.profile_theme == 'dark' else 'dark'
    db.session.commit()
    flash('Тема оформления обновлена')
    return redirect(request.referrer or url_for('profile'))


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


@app.route('/upgrade_card/<int:card_id>', methods=['POST'])
@login_required
def upgrade_card(card_id):
    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card_id).first_or_404()
    current_stars = int(user_card.star_level or 0)
    upgrade_cost = get_star_upgrade_cost(current_stars)

    if upgrade_cost is None:
        flash('У этой карточки уже максимальный уровень звёздности')
        return redirect(url_for('collection'))

    available_duplicates = max(0, (user_card.quantity or 0) - 1)
    if available_duplicates < upgrade_cost:
        flash(f'Для улучшения до {current_stars + 1}★ нужно ещё {upgrade_cost} повторок')
        return redirect(url_for('collection'))

    user_card.quantity -= upgrade_cost
    user_card.star_level = current_stars + 1
    db.session.commit()
    flash(f'Карточка «{user_card.card.name}» улучшена до {user_card.star_level}★')
    return redirect(url_for('collection'))

@app.route('/dev/add-coins/<int:amount>')
@login_required
def dev_add_coins(amount):
    # Защита: работает только в режиме разработки
    if not app.debug:
        flash("Функция доступна только в debug-режиме!")
        return redirect(url_for('profile'))
    
    current_user.coins += amount
    db.session.commit()
    flash(f"✅ Начислено {amount} монет. Текущий баланс: {current_user.coins}")
    return redirect(url_for('profile'))

@app.route('/quizzes')
@login_required
def quizzes():
    quizzes_list = Quiz.query.all()
    return render_template('quizzes.html', quizzes=quizzes_list)
@app.route('/quiz/<int:quiz_id>', methods=['GET', 'POST'])
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
    active_tab = request.args.get('tab', 'card_roulette')
    card_products = ShopItem.query.filter(ShopItem.image_url.in_(['teacher-pack'])).order_by(ShopItem.price.asc()).all()
    frame_packs = ShopItem.query.filter(ShopItem.image_url.in_(['gems-frame-pack', 'fire-frame-pack'])).order_by(ShopItem.price.asc()).all()
    return render_template(
        'shop.html',
        card_products=card_products,
        frame_packs=frame_packs,
        active_tab=active_tab,
        get_frame_pack_meta=get_frame_pack_meta,
    )


def draw_random_cards(quantity, pack_code='gems-pack'):
    cards = Card.query.all()
    if not cards:
        return []

    pack_tables = {
        'gems-pack': {'common': 70, 'rare': 22, 'epic': 7, 'legendary': 1},
        'card-roulette': {'common': 55, 'rare': 25, 'epic': 15, 'legendary': 5},
        'fire-pack': {'common': 45, 'rare': 30, 'epic': 18, 'legendary': 7},
    }
    table = pack_tables.get(pack_code, pack_tables['gems-pack'])
    weights = [table.get(card.rarity, 1) for card in cards]
    return random.choices(cards, weights=weights, k=quantity)


def draw_random_frames(quantity, user, collection='gems'):
    frames = [frame for frame in ShopItem.query.filter_by(type='frame').all() if get_frame_collection(frame) == collection]
    if not frames:
        return []

    compensation_map = {'gems': 35, 'fire': 45}
    compensation_value = compensation_map.get(collection, 35)
    results = []
    owned = set(get_owned_frame_codes(user))
    for _ in range(quantity):
        available = [frame for frame in frames if get_frame_code(frame) not in owned]
        pool = available or frames
        frame = random.choice(pool)
        was_new = get_frame_code(frame) not in owned
        if was_new:
            add_frame_to_user(user, frame)
            owned.add(get_frame_code(frame))
        results.append({'frame': frame, 'is_new': was_new, 'compensation': compensation_value if not was_new else 0})
    return results


@app.route('/open-pack', methods=['GET', 'POST'])
@login_required
def open_pack():
    item_id = request.args.get('item_id', type=int)
    selected_pack = None
    if item_id:
        selected_pack = ShopItem.query.filter(ShopItem.id == item_id, ShopItem.type.in_(['card_pack', 'card_roulette'])).first()
    if not selected_pack:
        selected_pack = ShopItem.query.filter_by(image_url='teacher-pack').first() or ShopItem.query.filter_by(type='card_pack').first_or_404()

    quantity_options = [1, 3, 5]

    if request.method == 'POST':
        quantity = request.form.get('quantity', type=int, default=1)
        if quantity not in quantity_options:
            quantity = 1

        total_price = selected_pack.price * quantity
        if current_user.coins < total_price:
            flash('Недостаточно монет для открытия выбранного количества пакетов')
            return redirect(url_for('open_pack', item_id=selected_pack.id))

        current_user.coins -= total_price
        dropped_cards = draw_random_cards(quantity, selected_pack.image_url or 'teacher-pack')
        dropped_ids = []
        for dropped_card in dropped_cards:
            add_card_to_user(current_user.id, dropped_card.id)
            dropped_ids.append(dropped_card.id)

        db.session.commit()
        session['last_pack_result'] = dropped_ids
        session['last_pack_item_id'] = selected_pack.id
        return redirect(url_for('pack_result'))

    return render_template('open_pack.html', card_pack=selected_pack, quantity_options=quantity_options)


@app.route('/open-frame-pack', methods=['GET', 'POST'])
@login_required
def open_frame_pack():
    item_id = request.args.get('item_id', type=int)
    frame_pack = None
    if item_id:
        frame_pack = ShopItem.query.filter(ShopItem.id == item_id, ShopItem.type == 'frame_pack').first()
    if not frame_pack:
        frame_pack = ShopItem.query.filter_by(image_url='gems-frame-pack').first_or_404()

    pack_meta = get_frame_pack_meta(frame_pack.image_url or 'gems-frame-pack')
    quantity_options = [1, 3, 5]

    if request.method == 'POST':
        quantity = request.form.get('quantity', type=int, default=1)
        if quantity not in quantity_options:
            quantity = 1

        total_price = frame_pack.price * quantity
        if current_user.coins < total_price:
            flash('Недостаточно монет для рулетки рамок')
            return redirect(url_for('open_frame_pack', item_id=frame_pack.id))

        preview_results = draw_random_frames(quantity, current_user, pack_meta['collection'])
        if not preview_results:
            flash('Для этой рулетки пока нет доступных рамочек. Добавьте изображения в папку Frames и перезапустите проект.')
            return redirect(url_for('open_frame_pack', item_id=frame_pack.id))

        current_user.coins -= total_price
        results = preview_results
        compensation_total = sum(item['compensation'] for item in results)
        if compensation_total:
            current_user.coins += compensation_total

        if current_user.avatar_frame == 'none':
            first_new = next((item for item in results if item['is_new']), None)
            if first_new:
                current_user.avatar_frame = get_frame_code(first_new['frame'])

        db.session.commit()
        session['last_frame_result'] = {
            'pack_item_id': frame_pack.id,
            'pack_code': frame_pack.image_url,
            'quantity': quantity,
            'results': [
                {
                    'item_id': item['frame'].id,
                    'is_new': item['is_new'],
                    'compensation': item['compensation'],
                }
                for item in results
            ]
        }
        return redirect(url_for('frame_pack_result'))

    return render_template('open_frame_pack.html', frame_pack=frame_pack, pack_meta=pack_meta, quantity_options=quantity_options)


@app.route('/frame-pack-result')
@login_required
def frame_pack_result():
    payload = session.pop('last_frame_result', None)
    if not payload:
        flash('Сначала откройте рулетку рамок')
        return redirect(url_for('open_frame_pack'))

    if isinstance(payload, list):
        payload = {'pack_code': 'gems-frame-pack', 'results': payload, 'pack_item_id': None}

    results = []
    for item in payload.get('results', []):
        shop_item = ShopItem.query.get(item['item_id'])
        if shop_item:
            results.append({'frame': shop_item, 'is_new': item['is_new'], 'compensation': item['compensation']})

    pack_meta = get_frame_pack_meta(payload.get('pack_code', 'gems-frame-pack'))
    return render_template('frame_pack_result.html', results=results, pack_meta=pack_meta, pack_item_id=payload.get('pack_item_id'), get_frame_asset_url=get_frame_asset_url, get_frame_code=get_frame_code)


@app.route('/buy_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def buy_item(item_id):
    item = ShopItem.query.get_or_404(item_id)

    if item.type in ['card_pack', 'card_roulette']:
        return redirect(url_for('open_pack', item_id=item.id))

    if item.type == 'frame_pack':
        return redirect(url_for('open_frame_pack', item_id=item.id))

    if item.type == 'theme':
        flash('Темы бесплатны и переключаются кнопкой в углу экрана')
        return redirect(url_for('shop'))

    if item.type == 'frame':
        frame_code = get_frame_code(item)
        if frame_code in get_owned_frame_codes(current_user):
            flash('Эта рамка уже куплена для вашего аккаунта')
            return redirect(url_for('shop'))

        if current_user.coins < item.price:
            flash('Недостаточно монет')
            return redirect(url_for('shop'))

        current_user.coins -= item.price
        add_frame_to_user(current_user, item)
        if current_user.avatar_frame == 'none':
            current_user.avatar_frame = frame_code
        db.session.commit()
        flash(f'Вы купили рамку: {item.name}')
        return redirect(url_for('profile'))

    flash('Этот товар пока недоступен')
    return redirect(url_for('shop'))


@app.route('/pack-result')
@login_required
def pack_result():
    card_ids = session.pop('last_pack_result', None)
    if not card_ids:
        flash('Сначала откройте пакет на странице открытия наборов')
        return redirect(url_for('open_pack'))

    if isinstance(card_ids, int):
        card_ids = [card_ids]

    cards_payload = []
    for card_id in card_ids:
        card = Card.query.get_or_404(card_id)
        user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card.id).first()
        cards_payload.append({
            'card': card,
            'duplicate_count': user_card.quantity if user_card else 1,
            'sale_price': RARITY_SELL_PRICES.get(card.rarity, 25)
        })

    rarest_order = {'common': 1, 'rare': 2, 'epic': 3, 'legendary': 4}
    top_rarity = max((item['card'].rarity for item in cards_payload), key=lambda rarity: rarest_order.get(rarity, 0))

    pack_item_id = session.get('last_pack_item_id')
    return render_template('pack_result.html', cards_payload=cards_payload, pack_count=len(cards_payload), top_rarity=top_rarity, pack_item_id=pack_item_id)


@app.route('/exchange', methods=['GET', 'POST'])
@login_required
def exchange():
    if request.method == 'POST':
        requested_card_id = request.form.get('requested_card_id', type=int)
        target_user_id = request.form.get('target_user_id', type=int)

        if not requested_card_id:
            flash('Выберите карточку, которую хотите получить')
            return redirect(url_for('exchange'))

        new_request = TradeRequest(
            requester_id=current_user.id,
            requested_card_id=requested_card_id,
            target_user_id=target_user_id or None,
            status='open'
        )
        db.session.add(new_request)
        db.session.commit()
        flash('Запрос на обмен создан')
        return redirect(url_for('exchange'))

    cards = Card.query.order_by(Card.name.asc()).all()
    open_requests = (
        TradeRequest.query.filter(TradeRequest.status == 'open', TradeRequest.requester_id != current_user.id)
        .order_by(TradeRequest.created_at.desc())
        .all()
    )
    my_requests = (
        TradeRequest.query.filter_by(requester_id=current_user.id)
        .order_by(TradeRequest.created_at.desc())
        .all()
    )
    incoming_offers = TradeOffer.query.filter_by(to_user_id=current_user.id, status='pending').order_by(TradeOffer.created_at.desc()).all()
    outgoing_offers = TradeOffer.query.filter_by(from_user_id=current_user.id).order_by(TradeOffer.created_at.desc()).all()
    return render_template(
        'exchange.html',
        cards=cards,
        open_requests=open_requests,
        my_requests=my_requests,
        incoming_offers=incoming_offers,
        outgoing_offers=outgoing_offers,
        get_card_letter=get_card_letter,
    )


@app.route('/exchange/propose/<int:target_user_id>/<int:requested_card_id>', methods=['GET', 'POST'])
@login_required
def propose_exchange(target_user_id, requested_card_id):
    target_user = User.query.get_or_404(target_user_id)
    if target_user.id == current_user.id:
        flash('Нельзя предлагать обмен самому себе')
        return redirect(url_for('exchange'))

    requested_user_card = UserCard.query.filter_by(user_id=target_user.id, card_id=requested_card_id).first_or_404()
    my_cards = UserCard.query.filter(UserCard.user_id == current_user.id, UserCard.quantity >= 1).order_by(UserCard.quantity.desc()).all()

    if request.method == 'POST':
        offered_card_id = request.form.get('offered_card_id', type=int)
        if not offered_card_id:
            flash('Сначала выберите свою карточку для обмена')
            return redirect(url_for('propose_exchange', target_user_id=target_user.id, requested_card_id=requested_card_id))

        own_card = UserCard.query.filter_by(user_id=current_user.id, card_id=offered_card_id).first()
        target_card = UserCard.query.filter_by(user_id=target_user.id, card_id=requested_card_id).first()
        if not own_card or own_card.quantity < 1:
            flash('У вас нет выбранной карточки')
            return redirect(url_for('propose_exchange', target_user_id=target_user.id, requested_card_id=requested_card_id))
        if not target_card or target_card.quantity < 1:
            flash('У пользователя больше нет этой карточки')
            return redirect(url_for('view_profile', user_id=target_user.id))

        offer = TradeOffer(from_user_id=current_user.id, to_user_id=target_user.id, offered_card_id=offered_card_id, requested_card_id=requested_card_id, status='pending')
        db.session.add(offer)
        matching_request = TradeRequest.query.filter_by(requester_id=target_user.id, requested_card_id=offered_card_id, status='open').first()
        if matching_request:
            matching_request.status = 'matched'
        db.session.commit()
        flash('Предложение обмена отправлено')
        return redirect(url_for('exchange'))

    return render_template('propose_exchange.html', target_user=target_user, requested_user_card=requested_user_card, my_cards=my_cards, get_card_letter=get_card_letter, get_card_stars_display=get_card_stars_display)


@app.route('/exchange/request/<int:request_id>/respond', methods=['GET', 'POST'])
@login_required
def respond_trade_request(request_id):
    trade_request = TradeRequest.query.get_or_404(request_id)
    if trade_request.requester_id == current_user.id or trade_request.status != 'open':
        flash('Этот запрос недоступен')
        return redirect(url_for('exchange'))

    own_requested_card = UserCard.query.filter_by(user_id=current_user.id, card_id=trade_request.requested_card_id).first()
    if not own_requested_card or own_requested_card.quantity < 1:
        flash('У вас нет карточки, которую хочет получить этот пользователь')
        return redirect(url_for('exchange'))

    target_cards = UserCard.query.filter(UserCard.user_id == trade_request.requester_id, UserCard.quantity >= 1).order_by(UserCard.quantity.desc()).all()

    if request.method == 'POST':
        wanted_from_requester = request.form.get('requested_card_id', type=int)
        if not wanted_from_requester:
            flash('Выберите карточку, которую хотите получить от пользователя')
            return redirect(url_for('respond_trade_request', request_id=request_id))

        requester_card = UserCard.query.filter_by(user_id=trade_request.requester_id, card_id=wanted_from_requester).first()
        if not requester_card or requester_card.quantity < 1:
            flash('У пользователя больше нет выбранной карточки')
            return redirect(url_for('respond_trade_request', request_id=request_id))

        offer = TradeOffer(from_user_id=current_user.id, to_user_id=trade_request.requester_id, offered_card_id=trade_request.requested_card_id, requested_card_id=wanted_from_requester, status='pending')
        db.session.add(offer)
        trade_request.status = 'matched'
        db.session.commit()
        flash('Вы откликнулись на запрос обмена')
        return redirect(url_for('exchange'))

    return render_template('respond_trade_request.html', trade_request=trade_request, target_cards=target_cards, get_card_letter=get_card_letter, get_card_stars_display=get_card_stars_display)


@app.route('/exchange/request/<int:request_id>/close', methods=['POST'])
@login_required
def close_trade_request(request_id):
    trade_request = TradeRequest.query.get_or_404(request_id)
    if trade_request.requester_id != current_user.id:
        flash('Закрыть можно только свой запрос')
        return redirect(url_for('exchange'))
    trade_request.status = 'closed'
    db.session.commit()
    flash('Запрос закрыт')
    return redirect(url_for('exchange'))


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
    TradeRequest.query.filter_by(requester_id=offer.to_user_id, requested_card_id=offer.offered_card_id, status='open').update({'status': 'matched'})
    TradeRequest.query.filter_by(requester_id=offer.from_user_id, requested_card_id=offer.requested_card_id, status='open').update({'status': 'matched'})
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
        cards_value = sum(get_user_card_wealth(uc) for uc in user.cards)
        enriched.append((user, user.coins + cards_value))
    enriched.sort(key=lambda item: item[1], reverse=True)
    return render_template('rating.html', users=enriched)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_database_schema()
        seed_data()
    app.run(debug=True)



print(app.instance_path)