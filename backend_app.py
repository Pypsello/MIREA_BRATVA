from __future__ import annotations

import json
import os
import random
from datetime import date, datetime
from functools import wraps
from typing import Dict, Iterable, List, Tuple

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///mirea_bratva.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


# -----------------------------
# Константы и конфиг гачи
# -----------------------------
CARD_PACK_PRICES = {1: 100, 3: 285, 5: 450}
FRAME_ROLL_PRICES = {"gems": 140, "fire": 190}
FRAME_DIRECT_PRICES = {"gems": 110, "fire": 160}
SELL_PRICE_BY_RARITY = {
    "common": 25,
    "rare": 55,
    "epic": 95,
    "legendary": 150,
}
UPGRADE_REQUIREMENTS = {
    1: 2,  # из 2 дубликатов делаем уровень 2
    2: 3,  # из 3 дубликатов делаем уровень 3
    3: 4,
}
CARD_RARITY_WEIGHTS = {
    "common": 60,
    "rare": 25,
    "epic": 10,
    "legendary": 5,
}
FRAME_POOLS = {
    "gems": [
        ("emerald-classic", 50),
        ("emerald-royal", 30),
        ("emerald-crown", 15),
        ("emerald-divine", 5),
    ],
    "fire": [
        ("fire-classic", 50),
        ("fire-lord", 30),
        ("fire-inferno", 15),
        ("fire-phoenix", 5),
    ],
}
FRAME_LABELS = {
    "none": "Без рамки",
    "emerald-classic": "Изумрудная классическая",
    "emerald-royal": "Изумрудная королевская",
    "emerald-crown": "Изумрудная корона",
    "emerald-divine": "Изумрудная божественная",
    "fire-classic": "Огненная классическая",
    "fire-lord": "Огненный лорд",
    "fire-inferno": "Огненное инферно",
    "fire-phoenix": "Феникс",
}


# -----------------------------
# Модели
# -----------------------------
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    coins = db.Column(db.Integer, default=100, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    profile_theme = db.Column(db.String(50), default="dark", nullable=False)
    avatar_frame = db.Column(db.String(50), default="none", nullable=False)
    last_daily_bonus_at = db.Column(db.DateTime, nullable=True)
    onboarding_seen = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Card(db.Model):
    __tablename__ = "cards"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default="")
    rarity = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(255), nullable=True)
    base_price = db.Column(db.Integer, default=50, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class UserCard(db.Model):
    __tablename__ = "user_cards"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    obtained_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "card_id", name="uq_user_card"),
        CheckConstraint("quantity >= 0", name="ck_user_cards_quantity_non_negative"),
    )

    user = db.relationship("User", backref=db.backref("cards", lazy=True, cascade="all, delete-orphan"))
    card = db.relationship("Card", backref=db.backref("owners", lazy=True))


class OwnedFrame(db.Model):
    __tablename__ = "owned_frames"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    frame_code = db.Column(db.String(50), nullable=False)
    obtained_by = db.Column(db.String(20), nullable=False, default="shop")
    obtained_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "frame_code", name="uq_user_frame"),
    )

    user = db.relationship("User", backref=db.backref("owned_frames", lazy=True, cascade="all, delete-orphan"))


class Quiz(db.Model):
    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    reward_coins = db.Column(db.Integer, default=50, nullable=False)
    passing_score = db.Column(db.Integer, default=60, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    option1 = db.Column(db.String(200), nullable=False)
    option2 = db.Column(db.String(200), nullable=False)
    option3 = db.Column(db.String(200), nullable=False)
    option4 = db.Column(db.String(200), nullable=False)
    correct_option = db.Column(db.Integer, nullable=False)

    quiz = db.relationship("Quiz", backref=db.backref("questions", lazy=True, cascade="all, delete-orphan"))


class QuizResult(db.Model):
    __tablename__ = "quiz_results"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TradeOffer(db.Model):
    __tablename__ = "trade_offers"

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    offered_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    requested_card_id = db.Column(db.Integer, db.ForeignKey("cards.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    responded_at = db.Column(db.DateTime, nullable=True)

    from_user = db.relationship("User", foreign_keys=[from_user_id], backref="sent_trade_offers")
    to_user = db.relationship("User", foreign_keys=[to_user_id], backref="received_trade_offers")
    offered_card = db.relationship("Card", foreign_keys=[offered_card_id])
    requested_card = db.relationship("Card", foreign_keys=[requested_card_id])


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, default="{}", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("logs", lazy=True))


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))


# -----------------------------
# Вспомогательные функции
# -----------------------------
def wants_json() -> bool:
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "message": message}), status


def json_ok(message: str, **payload):
    return jsonify({"ok": True, "message": message, **payload})


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        if not current_user.is_admin:
            if wants_json():
                return json_error("Доступ запрещён", 403)
            flash("Доступ запрещён")
            return redirect(url_for("index"))
        return func(*args, **kwargs)

    return wrapper


def log_action(action: str, user_id: int | None = None, **details) -> None:
    db.session.add(
        ActivityLog(
            user_id=user_id,
            action=action,
            details=json.dumps(details, ensure_ascii=False),
        )
    )


def get_or_create_user_card(user_id: int, card_id: int) -> UserCard:
    user_card = UserCard.query.filter_by(user_id=user_id, card_id=card_id).first()
    if user_card is None:
        user_card = UserCard(user_id=user_id, card_id=card_id, quantity=0, level=1)
        db.session.add(user_card)
    return user_card


def add_card_to_user(user_id: int, card_id: int, quantity: int = 1) -> UserCard:
    user_card = get_or_create_user_card(user_id, card_id)
    user_card.quantity += quantity
    return user_card


def remove_card_from_user(user_id: int, card_id: int, quantity: int = 1) -> bool:
    user_card = UserCard.query.filter_by(user_id=user_id, card_id=card_id).first()
    if user_card is None or user_card.quantity < quantity:
        return False
    user_card.quantity -= quantity
    if user_card.quantity <= 0:
        db.session.delete(user_card)
    return True


def user_owns_frame(user_id: int, frame_code: str) -> bool:
    return (
        OwnedFrame.query.filter_by(user_id=user_id, frame_code=frame_code).first()
        is not None
    )


def grant_frame(user_id: int, frame_code: str, obtained_by: str) -> bool:
    if user_owns_frame(user_id, frame_code):
        return False
    db.session.add(OwnedFrame(user_id=user_id, frame_code=frame_code, obtained_by=obtained_by))
    return True


def spend_coins(user: User, amount: int) -> bool:
    if amount < 0 or user.coins < amount:
        return False
    user.coins -= amount
    return True


def give_daily_bonus(user: User) -> Tuple[bool, int]:
    today = date.today()
    if user.last_daily_bonus_at and user.last_daily_bonus_at.date() == today:
        return False, 0
    bonus = 50
    user.coins += bonus
    user.last_daily_bonus_at = datetime.utcnow()
    log_action("daily_bonus", user.id, bonus=bonus)
    return True, bonus


def roll_card_by_weights() -> Card | None:
    cards = Card.query.filter_by(is_active=True).all()
    if not cards:
        return None
    weights = [CARD_RARITY_WEIGHTS.get(card.rarity, 1) for card in cards]
    return random.choices(cards, weights=weights, k=1)[0]


def roll_frame(frame_type: str) -> str:
    pool = FRAME_POOLS[frame_type]
    codes = [code for code, _ in pool]
    weights = [weight for _, weight in pool]
    return random.choices(codes, weights=weights, k=1)[0]


def serialize_user(user: User) -> Dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "coins": user.coins,
        "theme": user.profile_theme,
        "avatar_frame": user.avatar_frame,
        "is_admin": user.is_admin,
    }


def serialize_user_card(user_card: UserCard) -> Dict:
    return {
        "card_id": user_card.card_id,
        "name": user_card.card.name,
        "rarity": user_card.card.rarity,
        "subject": user_card.card.subject,
        "image_url": user_card.card.image_url,
        "quantity": user_card.quantity,
        "level": user_card.level,
    }


# -----------------------------
# Инициализация тестовых данных
# -----------------------------
def seed_data() -> None:
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            email="admin@example.com",
            is_admin=True,
            coins=9999,
            profile_theme="dark",
        )
        admin.set_password("admin123")
        db.session.add(admin)

    if not Card.query.first():
        cards = [
            Card(name="Иванов И.И.", description="Преподаватель математики", rarity="common", subject="Математика", base_price=50, image_url="/static/img/cards/ivanov.png"),
            Card(name="Петров П.П.", description="Преподаватель Python", rarity="rare", subject="Программирование", base_price=85, image_url="/static/img/cards/petrov.png"),
            Card(name="Сидорова А.А.", description="Преподаватель физики", rarity="epic", subject="Физика", base_price=130, image_url="/static/img/cards/sidorova.png"),
            Card(name="Кузнецов К.К.", description="Легендарный преподаватель ИИ", rarity="legendary", subject="ИИ", base_price=250, image_url="/static/img/cards/kuznetsov.png"),
        ]
        db.session.add_all(cards)

    if not Quiz.query.first():
        quiz_math = Quiz(subject="Математика", title="Базовый тест по математике", reward_coins=30, passing_score=60)
        quiz_py = Quiz(subject="Программирование", title="Основы Python", reward_coins=40, passing_score=60)
        db.session.add_all([quiz_math, quiz_py])
        db.session.flush()
        questions = [
            Question(quiz_id=quiz_math.id, text="Сколько будет 2 + 2?", option1="3", option2="4", option3="5", option4="6", correct_option=2),
            Question(quiz_id=quiz_math.id, text="Сколько градусов в прямом угле?", option1="45", option2="90", option3="120", option4="180", correct_option=2),
            Question(quiz_id=quiz_py.id, text="Какой тип у числа 10 в Python?", option1="str", option2="float", option3="int", option4="bool", correct_option=3),
            Question(quiz_id=quiz_py.id, text="Какой оператор чаще всего используют для цикла?", option1="for", option2="def", option3="class", option4="break", correct_option=1),
        ]
        db.session.add_all(questions)

    db.session.commit()


# -----------------------------
# Маршруты страниц
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    accept_pd = request.form.get("accept_pd") in {"on", "true", "1", "yes"}

    if not username or not email or not password:
        flash("Заполните все поля")
        return redirect(url_for("register"))
    if not accept_pd:
        flash("Нужно согласиться на обработку персональных данных")
        return redirect(url_for("register"))
    if User.query.filter_by(username=username).first():
        flash("Имя пользователя уже занято")
        return redirect(url_for("register"))
    if User.query.filter_by(email=email).first():
        flash("Email уже зарегистрирован")
        return redirect(url_for("register"))

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    log_action("register", None, username=username, email=email)
    db.session.commit()
    flash("Регистрация прошла успешно")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    login_value = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    user = User.query.filter(
        (User.username == login_value) | (User.email == login_value.lower())
    ).first()

    if user is None or not user.check_password(password):
        flash("Неверный логин или пароль")
        return redirect(url_for("login"))

    login_user(user)
    granted, bonus = give_daily_bonus(user)
    log_action("login", user.id, daily_bonus=bonus if granted else 0)
    db.session.commit()
    if granted:
        flash(f"Ежедневная награда: +{bonus} монет")
    return redirect(url_for("profile"))


@app.route("/logout")
@login_required
def logout():
    log_action("logout", current_user.id)
    db.session.commit()
    logout_user()
    return redirect(url_for("index"))


@app.route("/profile")
@login_required
def profile():
    frames = [frame.frame_code for frame in current_user.owned_frames]
    return render_template(
        "profile.html",
        user=current_user,
        available_frames=frames,
        frame_labels=FRAME_LABELS,
    )


@app.route("/profile/apply-frame/<frame_code>", methods=["POST"])
@login_required
def apply_frame(frame_code: str):
    if frame_code != "none" and not user_owns_frame(current_user.id, frame_code):
        flash("У вас нет такой рамки")
        return redirect(url_for("profile"))
    current_user.avatar_frame = frame_code
    log_action("apply_frame", current_user.id, frame_code=frame_code)
    db.session.commit()
    flash("Рамка применена")
    return redirect(url_for("profile"))


@app.route("/profile/theme", methods=["POST"])
@login_required
def change_theme():
    theme = request.form.get("theme", "dark").strip()
    if theme not in {"dark", "light", "neon"}:
        flash("Неизвестная тема")
        return redirect(url_for("profile"))
    current_user.profile_theme = theme
    log_action("change_theme", current_user.id, theme=theme)
    db.session.commit()
    flash("Тема обновлена")
    return redirect(url_for("profile"))


@app.route("/collection")
@login_required
def collection():
    rarity = request.args.get("rarity", "").strip()
    subject = request.args.get("subject", "").strip()

    query = UserCard.query.join(Card).filter(UserCard.user_id == current_user.id)
    if rarity:
        query = query.filter(Card.rarity == rarity)
    if subject:
        query = query.filter(Card.subject == subject)

    user_cards = query.order_by(Card.rarity.asc(), Card.name.asc()).all()
    return render_template("collection.html", user_cards=user_cards)


@app.route("/collection/sell/<int:card_id>", methods=["POST"])
@login_required
def sell_card(card_id: int):
    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card_id).first_or_404()
    if user_card.quantity <= 1:
        flash("Продать можно только дубликат")
        return redirect(url_for("collection"))

    price = SELL_PRICE_BY_RARITY.get(user_card.card.rarity, 25)
    user_card.quantity -= 1
    current_user.coins += price
    log_action("sell_card", current_user.id, card_id=card_id, price=price)
    db.session.commit()
    flash(f"Карточка продана за {price} монет")
    return redirect(url_for("collection"))


@app.route("/collection/upgrade/<int:card_id>", methods=["POST"])
@login_required
def upgrade_card(card_id: int):
    user_card = UserCard.query.filter_by(user_id=current_user.id, card_id=card_id).first_or_404()
    required_duplicates = UPGRADE_REQUIREMENTS.get(user_card.level)
    if required_duplicates is None:
        flash("Карточка уже максимального уровня")
        return redirect(url_for("collection"))
    if user_card.quantity <= required_duplicates:
        flash(f"Для улучшения нужно минимум {required_duplicates} дубликата(ов)")
        return redirect(url_for("collection"))

    user_card.quantity -= required_duplicates
    user_card.level += 1
    log_action(
        "upgrade_card",
        current_user.id,
        card_id=card_id,
        new_level=user_card.level,
        spent_duplicates=required_duplicates,
    )
    db.session.commit()
    flash(f"Карточка улучшена до уровня {user_card.level}")
    return redirect(url_for("collection"))


@app.route("/quizzes")
@login_required
def quizzes():
    return render_template("quizzes.html", quizzes=Quiz.query.filter_by(is_active=True).all())


@app.route("/quiz/<int:quiz_id>", methods=["GET", "POST"])
@login_required
def take_quiz(quiz_id: int):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = Question.query.filter_by(quiz_id=quiz.id).all()

    if request.method == "GET":
        return render_template("quiz.html", quiz=quiz, questions=questions)

    correct = 0
    total = len(questions)
    for question in questions:
        answer = request.form.get(f"question_{question.id}", type=int)
        if answer == question.correct_option:
            correct += 1

    score = int((correct / total) * 100) if total else 0
    passed = score >= quiz.passing_score
    db.session.add(QuizResult(user_id=current_user.id, quiz_id=quiz.id, score=score, passed=passed))
    if passed:
        current_user.coins += quiz.reward_coins
    log_action("take_quiz", current_user.id, quiz_id=quiz.id, score=score, passed=passed)
    db.session.commit()

    if passed:
        flash(f"Тест пройден. +{quiz.reward_coins} монет")
    else:
        flash(f"Тест не пройден. Результат: {score}%")
    return redirect(url_for("quizzes"))


@app.route("/shop")
@login_required
def shop():
    owned_frames = {frame.frame_code for frame in current_user.owned_frames}
    return render_template(
        "shop.html",
        card_pack_prices=CARD_PACK_PRICES,
        frame_roll_prices=FRAME_ROLL_PRICES,
        frame_direct_prices=FRAME_DIRECT_PRICES,
        owned_frames=owned_frames,
        frame_labels=FRAME_LABELS,
    )


@app.route("/shop/cards/roll", methods=["POST"])
@login_required
def roll_cards_page():
    count = request.form.get("count", type=int, default=1)
    if count not in CARD_PACK_PRICES:
        flash("Неверный размер прокрута")
        return redirect(url_for("shop"))

    price = CARD_PACK_PRICES[count]
    if not spend_coins(current_user, price):
        flash("Недостаточно монет")
        return redirect(url_for("shop"))

    results = []
    for _ in range(count):
        card = roll_card_by_weights()
        if card is None:
            current_user.coins += price
            flash("В базе нет карточек")
            return redirect(url_for("shop"))
        add_card_to_user(current_user.id, card.id)
        results.append(card.id)

    session["last_card_roll"] = results
    log_action("roll_cards", current_user.id, count=count, price=price, result_card_ids=results)
    db.session.commit()
    return redirect(url_for("card_roll_result"))


@app.route("/shop/cards/result")
@login_required
def card_roll_result():
    card_ids = session.pop("last_card_roll", None)
    if not card_ids:
        flash("Сначала открой рулетку карточек")
        return redirect(url_for("shop"))
    cards = Card.query.filter(Card.id.in_(card_ids)).all()
    cards_by_id = {card.id: card for card in cards}
    ordered_cards = [cards_by_id[card_id] for card_id in card_ids if card_id in cards_by_id]
    return render_template("pack_result.html", cards=ordered_cards, count=len(ordered_cards))


@app.route("/shop/frames/buy/<frame_code>", methods=["POST"])
@login_required
def buy_frame_direct(frame_code: str):
    frame_type = "gems" if frame_code.startswith("emerald") else "fire" if frame_code.startswith("fire") else None
    if frame_type is None:
        flash("Неизвестная рамка")
        return redirect(url_for("shop"))
    if user_owns_frame(current_user.id, frame_code):
        flash("Эта рамка уже куплена")
        return redirect(url_for("shop"))

    price = FRAME_DIRECT_PRICES[frame_type]
    if not spend_coins(current_user, price):
        flash("Недостаточно монет")
        return redirect(url_for("shop"))

    grant_frame(current_user.id, frame_code, "direct_purchase")
    current_user.avatar_frame = frame_code
    log_action("buy_frame_direct", current_user.id, frame_code=frame_code, price=price)
    db.session.commit()
    flash(f"Рамка {FRAME_LABELS.get(frame_code, frame_code)} куплена")
    return redirect(url_for("profile"))


@app.route("/shop/frames/roll/<frame_type>", methods=["POST"])
@login_required
def roll_frame_page(frame_type: str):
    if frame_type not in FRAME_ROLL_PRICES:
        flash("Неизвестный тип рулетки")
        return redirect(url_for("shop"))

    price = FRAME_ROLL_PRICES[frame_type]
    if not spend_coins(current_user, price):
        flash("Недостаточно монет")
        return redirect(url_for("shop"))

    frame_code = roll_frame(frame_type)
    is_new = grant_frame(current_user.id, frame_code, f"{frame_type}_roll")
    session["last_frame_roll"] = {"frame_code": frame_code, "is_new": is_new}
    log_action("roll_frame", current_user.id, frame_type=frame_type, price=price, frame_code=frame_code, is_new=is_new)
    db.session.commit()
    return redirect(url_for("frame_roll_result"))


@app.route("/shop/frames/result")
@login_required
def frame_roll_result():
    result = session.pop("last_frame_roll", None)
    if not result:
        flash("Сначала открой рулетку рамок")
        return redirect(url_for("shop"))
    return render_template("frame_result.html", result=result, frame_labels=FRAME_LABELS)


@app.route("/exchange", methods=["GET", "POST"])
@login_required
def exchange():
    if request.method == "POST":
        to_user_id = request.form.get("to_user_id", type=int)
        offered_card_id = request.form.get("offered_card_id", type=int)
        requested_card_id = request.form.get("requested_card_id", type=int)

        if not to_user_id or not offered_card_id or not requested_card_id:
            flash("Заполни все поля обмена")
            return redirect(url_for("exchange"))
        if to_user_id == current_user.id:
            flash("Нельзя обмениваться с самим собой")
            return redirect(url_for("exchange"))

        my_card = UserCard.query.filter_by(user_id=current_user.id, card_id=offered_card_id).first()
        target_card = UserCard.query.filter_by(user_id=to_user_id, card_id=requested_card_id).first()

        if my_card is None or my_card.quantity < 2:
            flash("Для обмена нужен хотя бы один дубликат вашей карточки")
            return redirect(url_for("exchange"))
        if target_card is None or target_card.quantity < 1:
            flash("У выбранного пользователя нет нужной карточки")
            return redirect(url_for("exchange"))

        offer = TradeOffer(
            from_user_id=current_user.id,
            to_user_id=to_user_id,
            offered_card_id=offered_card_id,
            requested_card_id=requested_card_id,
        )
        db.session.add(offer)
        log_action(
            "create_trade_offer",
            current_user.id,
            to_user_id=to_user_id,
            offered_card_id=offered_card_id,
            requested_card_id=requested_card_id,
        )
        db.session.commit()
        flash("Предложение обмена отправлено")
        return redirect(url_for("exchange"))

    users = User.query.filter(User.id != current_user.id).order_by(User.username.asc()).all()
    my_cards = UserCard.query.filter_by(user_id=current_user.id).all()
    incoming_offers = TradeOffer.query.filter_by(to_user_id=current_user.id, status="pending").order_by(TradeOffer.created_at.desc()).all()
    outgoing_offers = TradeOffer.query.filter_by(from_user_id=current_user.id).order_by(TradeOffer.created_at.desc()).all()
    return render_template(
        "exchange.html",
        users=users,
        my_cards=my_cards,
        incoming_offers=incoming_offers,
        outgoing_offers=outgoing_offers,
    )


@app.route("/exchange/accept/<int:offer_id>", methods=["POST"])
@login_required
def accept_exchange(offer_id: int):
    offer = TradeOffer.query.get_or_404(offer_id)
    if offer.to_user_id != current_user.id or offer.status != "pending":
        flash("Обмен недоступен")
        return redirect(url_for("exchange"))

    sender_card = UserCard.query.filter_by(user_id=offer.from_user_id, card_id=offer.offered_card_id).first()
    receiver_card = UserCard.query.filter_by(user_id=offer.to_user_id, card_id=offer.requested_card_id).first()

    if sender_card is None or sender_card.quantity < 2:
        offer.status = "cancelled"
        offer.responded_at = datetime.utcnow()
        db.session.commit()
        flash("У отправителя больше нет дубликата для обмена")
        return redirect(url_for("exchange"))

    if receiver_card is None or receiver_card.quantity < 1:
        offer.status = "cancelled"
        offer.responded_at = datetime.utcnow()
        db.session.commit()
        flash("У вас больше нет карточки для обмена")
        return redirect(url_for("exchange"))

    remove_card_from_user(offer.from_user_id, offer.offered_card_id, 1)
    remove_card_from_user(offer.to_user_id, offer.requested_card_id, 1)
    add_card_to_user(offer.from_user_id, offer.requested_card_id, 1)
    add_card_to_user(offer.to_user_id, offer.offered_card_id, 1)

    offer.status = "accepted"
    offer.responded_at = datetime.utcnow()
    log_action("accept_trade_offer", current_user.id, offer_id=offer.id)
    db.session.commit()
    flash("Обмен выполнен")
    return redirect(url_for("exchange"))


@app.route("/exchange/reject/<int:offer_id>", methods=["POST"])
@login_required
def reject_exchange(offer_id: int):
    offer = TradeOffer.query.get_or_404(offer_id)
    if offer.to_user_id != current_user.id or offer.status != "pending":
        flash("Обмен недоступен")
        return redirect(url_for("exchange"))

    offer.status = "rejected"
    offer.responded_at = datetime.utcnow()
    log_action("reject_trade_offer", current_user.id, offer_id=offer.id)
    db.session.commit()
    flash("Предложение отклонено")
    return redirect(url_for("exchange"))


@app.route("/rating")
@login_required
def rating():
    rows = []
    users = User.query.order_by(User.coins.desc()).limit(100).all()
    for user in users:
        card_value = sum((uc.card.base_price or 0) * uc.quantity for uc in user.cards)
        rows.append({"user": user, "score": user.coins + card_value})
    rows.sort(key=lambda item: item["score"], reverse=True)
    return render_template("rating.html", rows=rows)


# -----------------------------
# JSON API
# -----------------------------
@app.route("/api/me")
@login_required
def api_me():
    owned_frames = [frame.frame_code for frame in current_user.owned_frames]
    return json_ok("Профиль загружен", user=serialize_user(current_user), owned_frames=owned_frames)


@app.route("/api/collection")
@login_required
def api_collection():
    cards = [serialize_user_card(item) for item in UserCard.query.filter_by(user_id=current_user.id).all()]
    return json_ok("Коллекция загружена", items=cards)


@app.route("/api/shop")
@login_required
def api_shop():
    return json_ok(
        "Магазин загружен",
        cards_roulette=CARD_PACK_PRICES,
        frame_roulette=FRAME_ROLL_PRICES,
        frame_direct=FRAME_DIRECT_PRICES,
        owned_frames=[frame.frame_code for frame in current_user.owned_frames],
    )


@app.route("/api/shop/cards/roll", methods=["POST"])
@login_required
def api_roll_cards():
    payload = request.get_json(silent=True) or {}
    count = int(payload.get("count", 1))
    if count not in CARD_PACK_PRICES:
        return json_error("Неверное количество прокрутов")
    price = CARD_PACK_PRICES[count]
    if not spend_coins(current_user, price):
        return json_error("Недостаточно монет", 400)

    result = []
    for _ in range(count):
        card = roll_card_by_weights()
        if card is None:
            current_user.coins += price
            return json_error("В базе нет карточек", 500)
        add_card_to_user(current_user.id, card.id)
        result.append({
            "card_id": card.id,
            "name": card.name,
            "rarity": card.rarity,
            "subject": card.subject,
            "image_url": card.image_url,
        })

    log_action("api_roll_cards", current_user.id, count=count, price=price)
    db.session.commit()
    return json_ok("Рулетка карточек прокручена", spent=price, coins=current_user.coins, results=result)


@app.route("/api/shop/frames/roll", methods=["POST"])
@login_required
def api_roll_frame():
    payload = request.get_json(silent=True) or {}
    frame_type = str(payload.get("type", "gems"))
    if frame_type not in FRAME_ROLL_PRICES:
        return json_error("Неизвестный тип рулетки")
    price = FRAME_ROLL_PRICES[frame_type]
    if not spend_coins(current_user, price):
        return json_error("Недостаточно монет")

    frame_code = roll_frame(frame_type)
    is_new = grant_frame(current_user.id, frame_code, f"{frame_type}_roll")
    log_action("api_roll_frame", current_user.id, frame_type=frame_type, frame_code=frame_code, is_new=is_new)
    db.session.commit()
    return json_ok(
        "Рулетка рамок прокручена",
        spent=price,
        coins=current_user.coins,
        result={
            "frame_code": frame_code,
            "frame_name": FRAME_LABELS.get(frame_code, frame_code),
            "is_new": is_new,
        },
    )


@app.route("/api/exchange/users/<int:user_id>/cards")
@login_required
def api_user_cards_for_exchange(user_id: int):
    if user_id == current_user.id:
        items = UserCard.query.filter_by(user_id=current_user.id).all()
    else:
        items = UserCard.query.filter_by(user_id=user_id).all()
    return json_ok("Карточки загружены", items=[serialize_user_card(item) for item in items])


@app.route("/api/admin/cards", methods=["POST"])
@login_required
@admin_required
def api_admin_create_card():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    rarity = str(payload.get("rarity", "common")).strip()
    subject = str(payload.get("subject", "")).strip()
    if not name or not subject:
        return json_error("name и subject обязательны")

    card = Card(
        name=name,
        description=str(payload.get("description", "")),
        rarity=rarity,
        subject=subject,
        image_url=payload.get("image_url"),
        base_price=int(payload.get("base_price", 50)),
    )
    db.session.add(card)
    log_action("admin_create_card", current_user.id, name=name, rarity=rarity)
    db.session.commit()
    return json_ok("Карточка создана", card_id=card.id)


@app.route("/api/admin/logs")
@login_required
@admin_required
def api_admin_logs():
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(200).all()
    items = [
        {
            "id": log.id,
            "user_id": log.user_id,
            "action": log.action,
            "details": json.loads(log.details or "{}"),
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
    return json_ok("Логи загружены", items=items)


# -----------------------------
# Команды и запуск
# -----------------------------
@app.cli.command("seed")
def seed_command():
    seed_data()
    print("Данные добавлены")


@app.cli.command("create-admin")
def create_admin_command():
    username = os.environ.get("ADMIN_USERNAME", "admin")
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, email=email, is_admin=True, coins=9999)
        user.set_password(password)
        db.session.add(user)
    else:
        user.is_admin = True
        user.email = email
        user.set_password(password)
    db.session.commit()
    print(f"Админ {username} готов")


with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=True)
