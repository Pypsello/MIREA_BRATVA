from app import app, db
from app import User, Card, Quiz, Question, ShopItem
from werkzeug.security import generate_password_hash
import json

def init_database():
    with app.app_context():
        # Удаляем все таблицы и создаем заново
        db.drop_all()
        db.create_all()
        
        # Создаем тестового пользователя
        test_user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('password123'),
            coins=500
        )
        db.session.add(test_user)
        
        # Создаем карточки
        cards_data = [
            ('Иван Иванов', 'Профессор математики', 'legendary', 'Математика'),
            ('Петр Петров', 'Доцент физики', 'epic', 'Физика'),
            ('Мария Сидорова', 'Преподаватель программирования', 'rare', 'Программирование'),
            ('Анна Смирнова', 'Ассистент химии', 'common', 'Химия'),
            ('Дмитрий Козлов', 'Профессор информатики', 'legendary', 'Информатика'),
            ('Елена Попова', 'Доцент биологии', 'epic', 'Биология'),
            ('Алексей Новиков', 'Преподаватель истории', 'rare', 'История'),
            ('Ольга Морозова', 'Ассистент английского языка', 'common', 'Английский'),
        ]
        
        for name, desc, rarity, subject in cards_data:
            card = Card(name=name, description=desc, rarity=rarity, subject=subject)
            db.session.add(card)
        
        # Создаем квиз
        quiz = Quiz(subject='Математика', title='Основы математики', reward_coins=50, passing_score=60)
        db.session.add(quiz)
        db.session.flush()
        
        # Вопросы для квиза
        questions_data = [
            ('Сколько будет 2 + 2?', '3', '4', '5', '6', 2),
            ('Корень квадратный из 64?', '6', '7', '8', '9', 3),
            ('Производная от x^2?', 'x', '2x', '2', 'x^2', 2),
        ]
        
        for text, opt1, opt2, opt3, opt4, correct in questions_data:
            question = Question(
                quiz_id=quiz.id,
                text=text,
                option1=opt1,
                option2=opt2,
                option3=opt3,
                option4=opt4,
                correct_option=correct
            )
            db.session.add(question)
        
        # Предметы в магазине
        shop_items = [
            ShopItem(name='Темная тема', type='theme', price=100, description='Темный стиль для профиля'),
            ShopItem(name='Светлая тема', type='theme', price=100, description='Светлый стиль для профиля'),
            ShopItem(name='Золотая рамка', type='frame', price=150, description='Золотая рамка для аватара'),
            ShopItem(name='Серебряная рамка', type='frame', price=100, description='Серебряная рамка для аватара'),
            ShopItem(name='Базовый пакет', type='card_pack', price=50, 
                    description='Случайная карточка',
                    pack_rarity_chances=json.dumps({'common': 60, 'rare': 25, 'epic': 10, 'legendary': 5})),
        ]
        
        for item in shop_items:
            db.session.add(item)
        
        db.session.commit()
        print("База данных успешно инициализирована!")
        print("Тестовый пользователь: testuser / password123")

if __name__ == '__main__':
    init_database()