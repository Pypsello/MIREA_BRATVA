from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import random

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    coins = db.Column(db.Integer, default=100)
    profile_theme = db.Column(db.String(50), default='default')
    avatar_frame = db.Column(db.String(50), default='none')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_daily_bonus = db.Column(db.DateTime, default=None)
    
    # Связи
    cards = db.relationship('UserCard', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def get_total_coins_earned(self):
        # Сумма всех полученных монет (для рейтинга)
        total = self.coins + 100 + len(self.cards) * 10
        return total

class Card(db.Model):
    __tablename__ = 'card'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    rarity = db.Column(db.String(20), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200))
    base_price = db.Column(db.Integer, default=50)
    upgrade_level = db.Column(db.Integer, default=1)
    
    # Связи
    user_cards = db.relationship('UserCard', backref='card', lazy=True, cascade='all, delete-orphan')

class UserCard(db.Model):
    __tablename__ = 'user_card'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    is_favorite = db.Column(db.Boolean, default=False)
    level = db.Column(db.Integer, default=1)
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow)

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

class QuizResult(db.Model):
    __tablename__ = 'quiz_result'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    passed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

class Friendship(db.Model):
    __tablename__ = 'friendship'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи для доступа к объектам пользователей
    user = db.relationship('User', foreign_keys=[user_id], backref='friendships')
    friend = db.relationship('User', foreign_keys=[friend_id])

class ExchangeOffer(db.Model):
    __tablename__ = 'exchange_offer'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_card_id = db.Column(db.Integer, db.ForeignKey('user_card.id'), nullable=False)
    receiver_card_id = db.Column(db.Integer, db.ForeignKey('user_card.id'), nullable=True)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Связи
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])
    sender_card = db.relationship('UserCard', foreign_keys=[sender_card_id])
    receiver_card = db.relationship('UserCard', foreign_keys=[receiver_card_id])

class ShopItem(db.Model):
    __tablename__ = 'shop_item'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(200))
    
    # Для пакетов карточек
    pack_rarity_chances = db.Column(db.String(200))
    
    @staticmethod
    def get_card_pack():
        return ShopItem.query.filter_by(type='card_pack').first()