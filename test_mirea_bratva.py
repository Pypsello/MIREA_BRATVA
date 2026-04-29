"""
MIREA_BRATVA — Тестирование проекта
27 тестовых сценариев. Flask + sqlite3 + unittest.
"""
import unittest, sqlite3, os, json, time, tempfile
from flask import Flask, session, redirect, request, flash, g, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    app = Flask(__name__)
    app.config.update(SECRET_KEY='test-key', TESTING=True, DB_PATH=db_path)
    STAR_COSTS = [3,6,9,15,30,60,100]
    SELL_PRICES = {'common':25,'rare':50,'epic':75,'legendary':90}

    def get_db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DB_PATH'], check_same_thread=False)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(exc):
        db = g.pop('db', None)
        if db: db.close()

    db = sqlite3.connect(db_path)
    db.executescript("""
        CREATE TABLE user(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,coins INTEGER DEFAULT 100,
            bio TEXT DEFAULT '',avatar_frame TEXT DEFAULT 'none',avatar_icon TEXT DEFAULT 'letter',
            owned_frames TEXT DEFAULT '[]',profile_theme TEXT DEFAULT 'dark');
        CREATE TABLE card(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,description TEXT,
            rarity TEXT NOT NULL,subject TEXT NOT NULL,base_price INTEGER DEFAULT 50);
        CREATE TABLE user_card(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,card_id INTEGER,
            quantity INTEGER DEFAULT 1,star_level INTEGER DEFAULT 0);
        CREATE TABLE quiz(id INTEGER PRIMARY KEY AUTOINCREMENT,subject TEXT,title TEXT,
            reward_coins INTEGER DEFAULT 50,passing_score INTEGER DEFAULT 60);
        CREATE TABLE question(id INTEGER PRIMARY KEY AUTOINCREMENT,quiz_id INTEGER,text TEXT,
            option1 TEXT,option2 TEXT,option3 TEXT,option4 TEXT,correct_option INTEGER);
        CREATE TABLE quiz_result(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,
            quiz_id INTEGER,score INTEGER,passed INTEGER DEFAULT 0);
        CREATE TABLE trade_offer(id INTEGER PRIMARY KEY AUTOINCREMENT,from_user_id INTEGER,
            to_user_id INTEGER,offered_card_id INTEGER,requested_card_id INTEGER,
            status TEXT DEFAULT 'pending');
        CREATE TABLE wishlist_item(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,card_id INTEGER);
        CREATE TABLE shop_item(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,type TEXT,
            price INTEGER,description TEXT,image_url TEXT);
    """)
    db.execute("INSERT INTO card VALUES(1,'Иванов И.И.','Математик','common','Математика',50)")
    db.execute("INSERT INTO card VALUES(2,'Петров П.П.','Программист','rare','Программирование',80)")
    db.execute("INSERT INTO card VALUES(3,'Сидорова А.А.','Физик','epic','Физика',120)")
    db.execute("INSERT INTO card VALUES(4,'Кузнецов К.К.','ИИ','legendary','ИИ',250)")
    db.execute("INSERT INTO quiz VALUES(1,'Математика','Базовый тест',30,60)")
    db.execute("INSERT INTO question VALUES(1,1,'2+2?','3','4','5','6',2)")
    db.execute("INSERT INTO question VALUES(2,1,'Прямой угол?','45','90','120','180',2)")
    db.execute("INSERT INTO shop_item VALUES(1,'Рулетка','card_pack',100,'Пак','teacher-pack')")
    db.commit(); db.close()

    @app.route('/register', methods=['GET','POST'])
    def register():
        if request.method=='GET': return 'register_page'
        db=get_db(); u=request.form.get('username','').strip()
        e=request.form.get('email','').strip(); p=request.form.get('password','')
        if not u or not e or not p: flash('Заполните все поля'); return redirect('/register')
        if db.execute("SELECT id FROM user WHERE username=?",(u,)).fetchone():
            flash('Имя занято'); return redirect('/register')
        if db.execute("SELECT id FROM user WHERE email=?",(e,)).fetchone():
            flash('Email занят'); return redirect('/register')
        db.execute("INSERT INTO user(username,email,password_hash)VALUES(?,?,?)",
                   (u,e,generate_password_hash(p))); db.commit()
        flash('Регистрация успешна!'); return redirect('/login')

    @app.route('/login', methods=['GET','POST'])
    def login():
        if request.method=='GET': return 'login_page'
        db=get_db(); u=request.form.get('username','').strip(); p=request.form.get('password','')
        user=db.execute("SELECT * FROM user WHERE username=?",(u,)).fetchone()
        if user and check_password_hash(user['password_hash'],p):
            session['user_id']=user['id']; session['username']=user['username']
            return redirect('/profile')
        flash('Неверный логин/пароль'); return redirect('/login')

    @app.route('/logout')
    def logout(): session.clear(); return redirect('/')

    @app.route('/profile')
    def profile():
        if 'user_id' not in session: return redirect('/login')
        db=get_db(); u=db.execute("SELECT * FROM user WHERE id=?",(session['user_id'],)).fetchone()
        return jsonify(dict(u))

    @app.route('/profile/update', methods=['POST'])
    def update_profile():
        if 'user_id' not in session: return redirect('/login')
        db=get_db(); bio=request.form.get('bio','').strip()[:400]
        db.execute("UPDATE user SET bio=? WHERE id=?",(bio,session['user_id'])); db.commit()
        return redirect('/profile')

    @app.route('/quiz/<int:qid>', methods=['POST'])
    def take_quiz(qid):
        if 'user_id' not in session: return redirect('/login')
        db=get_db(); quiz=db.execute("SELECT * FROM quiz WHERE id=?",(qid,)).fetchone()
        if not quiz: return "Not found",404
        qs=db.execute("SELECT * FROM question WHERE quiz_id=?",(qid,)).fetchall()
        correct=sum(1 for q in qs if request.form.get(f'question_{q["id"]}') and
                    int(request.form.get(f'question_{q["id"]}'))==q['correct_option'])
        score=int((correct/len(qs))*100) if qs else 0; passed=score>=quiz['passing_score']
        db.execute("INSERT INTO quiz_result(user_id,quiz_id,score,passed)VALUES(?,?,?,?)",
                   (session['user_id'],qid,score,int(passed)))
        if passed:
            db.execute("UPDATE user SET coins=coins+? WHERE id=?",(quiz['reward_coins'],session['user_id']))
        db.commit(); return redirect('/quizzes')

    @app.route('/quizzes')
    def quizzes(): return 'quizzes_page'
    @app.route('/shop')
    def shop(): return 'shop_page'

    @app.route('/open-pack', methods=['POST'])
    def open_pack():
        if 'user_id' not in session: return redirect('/login')
        import random; db=get_db()
        qty=int(request.form.get('quantity',1))
        if qty not in [1,3,5]: qty=1
        pack=db.execute("SELECT * FROM shop_item WHERE image_url='teacher-pack'").fetchone()
        total=pack['price']*qty
        user=db.execute("SELECT * FROM user WHERE id=?",(session['user_id'],)).fetchone()
        if user['coins']<total: flash('Недостаточно монет'); return redirect('/shop')
        db.execute("UPDATE user SET coins=coins-? WHERE id=?",(total,session['user_id']))
        cards=db.execute("SELECT * FROM card").fetchall()
        wt=[{'common':55,'rare':25,'epic':15,'legendary':5}.get(c['rarity'],1) for c in cards]
        dropped=random.choices(cards,weights=wt,k=qty); result=[]
        for c in dropped:
            ex=db.execute("SELECT * FROM user_card WHERE user_id=? AND card_id=?",
                          (session['user_id'],c['id'])).fetchone()
            if ex: db.execute("UPDATE user_card SET quantity=quantity+1 WHERE id=?",(ex['id'],))
            else: db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,1,0)",
                             (session['user_id'],c['id']))
            result.append({'id':c['id'],'name':c['name'],'rarity':c['rarity']})
        db.commit(); return jsonify({'dropped':result})

    @app.route('/sell_card/<int:cid>', methods=['POST'])
    def sell_card(cid):
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        uc=db.execute("SELECT uc.*,c.rarity FROM user_card uc JOIN card c ON uc.card_id=c.id "
                      "WHERE uc.user_id=? AND uc.card_id=?",(session['user_id'],cid)).fetchone()
        if not uc: return "Not found",404
        if uc['quantity']<=1: return jsonify({'error':'only_duplicates'}),400
        sp=SELL_PRICES.get(uc['rarity'],25)
        db.execute("UPDATE user_card SET quantity=quantity-1 WHERE user_id=? AND card_id=?",
                   (session['user_id'],cid))
        db.execute("UPDATE user SET coins=coins+? WHERE id=?",(sp,session['user_id']))
        db.commit(); return jsonify({'sold':True,'price':sp})

    @app.route('/upgrade_card/<int:cid>', methods=['POST'])
    def upgrade_card(cid):
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        uc=db.execute("SELECT * FROM user_card WHERE user_id=? AND card_id=?",
                      (session['user_id'],cid)).fetchone()
        if not uc: return "Not found",404
        stars=uc['star_level'] or 0
        if stars>=len(STAR_COSTS): return jsonify({'error':'max_level'}),400
        cost=STAR_COSTS[stars]; dupes=max(0,(uc['quantity'] or 0)-1)
        if dupes<cost: return jsonify({'error':'insufficient','need':cost,'have':dupes}),400
        db.execute("UPDATE user_card SET quantity=quantity-?,star_level=? WHERE user_id=? AND card_id=?",
                   (cost,stars+1,session['user_id'],cid))
        db.commit(); return jsonify({'star_level':stars+1})

    @app.route('/wishlist/toggle/<int:cid>', methods=['POST'])
    def toggle_wishlist(cid):
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        ex=db.execute("SELECT id FROM wishlist_item WHERE user_id=? AND card_id=?",
                      (session['user_id'],cid)).fetchone()
        if ex: db.execute("DELETE FROM wishlist_item WHERE id=?",(ex['id'],)); a='removed'
        else: db.execute("INSERT INTO wishlist_item(user_id,card_id)VALUES(?,?)",
                         (session['user_id'],cid)); a='added'
        db.commit(); return jsonify({'action':a,'card_id':cid})

    @app.route('/wishlist')
    def wishlist():
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        items=db.execute("SELECT c.* FROM wishlist_item w JOIN card c ON w.card_id=c.id WHERE w.user_id=?",
                         (session['user_id'],)).fetchall()
        return jsonify([dict(i) for i in items])

    @app.route('/trade/create', methods=['POST'])
    def create_trade():
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        db.execute("INSERT INTO trade_offer(from_user_id,to_user_id,offered_card_id,requested_card_id)"
                   "VALUES(?,?,?,?)",(session['user_id'],int(request.form['to_user_id']),
                   int(request.form['offered_card_id']),int(request.form['requested_card_id'])))
        db.commit(); return jsonify({'status':'pending'})

    @app.route('/collection')
    def collection():
        if 'user_id' not in session: return redirect('/login')
        db=get_db()
        cards=db.execute("SELECT uc.*,c.name,c.rarity,c.base_price FROM user_card uc "
                         "JOIN card c ON uc.card_id=c.id WHERE uc.user_id=?",
                         (session['user_id'],)).fetchall()
        return jsonify([dict(c) for c in cards])

    @app.route('/rating')
    def rating():
        db=get_db()
        users=db.execute("""SELECT u.id,u.username,u.coins,
            COALESCE(SUM(c.base_price*uc.quantity),0) as cw
            FROM user u LEFT JOIN user_card uc ON u.id=uc.user_id
            LEFT JOIN card c ON uc.card_id=c.id GROUP BY u.id
            ORDER BY (u.coins+COALESCE(SUM(c.base_price*uc.quantity),0)) DESC""").fetchall()
        return jsonify([{'username':u['username'],'wealth':u['coins']+u['cw']} for u in users])

    @app.route('/reset-password', methods=['GET','POST'])
    def reset_password():
        if request.method=='GET': return 'reset_page'
        db=get_db(); u=request.form.get('username','').strip()
        e=request.form.get('email','').strip()
        np=request.form.get('new_password',''); cp=request.form.get('confirm_password','')
        if not u or not e or not np or not cp: return jsonify({'error':'empty'}),400
        if np!=cp: return jsonify({'error':'mismatch'}),400
        if len(np)<4: return jsonify({'error':'short'}),400
        user=db.execute("SELECT * FROM user WHERE username=? AND email=?",(u,e)).fetchone()
        if not user: return jsonify({'error':'not_found'}),404
        db.execute("UPDATE user SET password_hash=? WHERE id=?",(generate_password_hash(np),user['id']))
        db.commit(); return jsonify({'success':True})

    return app


class TestMireaBratva(unittest.TestCase):
    def setUp(self):
        self.app=create_app(); self.client=self.app.test_client()
        self.ctx=self.app.app_context(); self.ctx.push()
    def tearDown(self):
        self.ctx.pop()
        try: os.unlink(self.app.config['DB_PATH'])
        except: pass
    def _db(self):
        db=sqlite3.connect(self.app.config['DB_PATH']); db.row_factory=sqlite3.Row; return db
    def _reg(self,u='testuser',e='test@m.ru',p='pass1234'):
        return self.client.post('/register',data={'username':u,'email':e,'password':p},follow_redirects=True)
    def _login(self,u='testuser',p='pass1234'):
        return self.client.post('/login',data={'username':u,'password':p},follow_redirects=True)
    def _reg_login(self,u='testuser',e='test@m.ru',p='pass1234'):
        self._reg(u,e,p); self._login(u,p)

    def test_01_register_positive(self):
        """TC-01: Успешная регистрация"""
        self._reg('new','new@m.ru','p1234')
        db=self._db(); u=db.execute("SELECT * FROM user WHERE username='new'").fetchone(); db.close()
        self.assertIsNotNone(u); self.assertEqual(u['coins'],100)

    def test_02_register_dup_username(self):
        """TC-02: Дубликат username"""
        self._reg('dup','d1@m.ru','p'); self._reg('dup','d2@m.ru','p')
        db=self._db(); c=db.execute("SELECT COUNT(*)as c FROM user WHERE username='dup'").fetchone()['c']; db.close()
        self.assertEqual(c,1)

    def test_03_register_dup_email(self):
        """TC-03: Дубликат email"""
        self._reg('a','s@m.ru','p'); self._reg('b','s@m.ru','p')
        db=self._db(); c=db.execute("SELECT COUNT(*)as c FROM user WHERE email='s@m.ru'").fetchone()['c']; db.close()
        self.assertEqual(c,1)

    def test_04_register_empty(self):
        """TC-04: Пустые поля — пользователь не создаётся"""
        self.client.post('/register',data={'username':'','email':'','password':''})
        db=self._db(); c=db.execute("SELECT COUNT(*)as c FROM user").fetchone()['c']; db.close()
        self.assertEqual(c,0)

    def test_05_login_positive(self):
        """TC-05: Успешный вход — сессия создаётся"""
        self._reg(); self._login()
        with self.client.session_transaction() as s: self.assertIn('user_id',s)

    def test_06_login_wrong_pw(self):
        """TC-06: Неверный пароль — сессия не создаётся"""
        self._reg(); self._login('testuser','wrong')
        with self.client.session_transaction() as s: self.assertNotIn('user_id',s)

    def test_07_login_nonexistent(self):
        """TC-07: Несуществующий пользователь"""
        self._login('nobody','p')
        with self.client.session_transaction() as s: self.assertNotIn('user_id',s)

    def test_08_quiz_pass(self):
        """TC-08: Тест пройден — +30 монет"""
        self._reg_login()
        db=self._db(); before=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']
        qs=db.execute("SELECT * FROM question WHERE quiz_id=1").fetchall(); db.close()
        self.client.post('/quiz/1',data={f'question_{q["id"]}':str(q['correct_option']) for q in qs},follow_redirects=True)
        db=self._db(); after=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']; db.close()
        self.assertEqual(after, before+30)

    def test_09_quiz_fail(self):
        """TC-09: Тест провален — монеты не начислены"""
        self._reg_login()
        db=self._db(); before=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']
        qs=db.execute("SELECT * FROM question WHERE quiz_id=1").fetchall(); db.close()
        self.client.post('/quiz/1',data={f'question_{q["id"]}':str((q['correct_option']%4)+1) for q in qs},follow_redirects=True)
        db=self._db(); after=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']; db.close()
        self.assertEqual(after, before)

    def test_10_buy_pack(self):
        """TC-10: Покупка 1 пака — карточка получена, -100 монет"""
        self._reg_login()
        rv=self.client.post('/open-pack',data={'quantity':'1'}); d=json.loads(rv.data)
        self.assertEqual(len(d['dropped']),1)
        db=self._db(); coins=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']; db.close()
        self.assertEqual(coins,0)

    def test_11_buy_pack_no_coins(self):
        """TC-11: Покупка при 0 монет — отказ"""
        self._reg_login()
        db=self._db(); db.execute("UPDATE user SET coins=0 WHERE username='testuser'"); db.commit(); db.close()
        self.client.post('/open-pack',data={'quantity':'1'},follow_redirects=True)
        db=self._db(); c=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']; db.close()
        self.assertEqual(c,0)

    def test_12_buy_pack_x3(self):
        """TC-12: Покупка 3 паков — 3 карточки, -300 монет"""
        self._reg_login()
        db=self._db(); db.execute("UPDATE user SET coins=500 WHERE username='testuser'"); db.commit(); db.close()
        rv=self.client.post('/open-pack',data={'quantity':'3'}); d=json.loads(rv.data)
        self.assertEqual(len(d['dropped']),3)
        db=self._db(); c=db.execute("SELECT coins FROM user WHERE username='testuser'").fetchone()['coins']; db.close()
        self.assertEqual(c,200)

    def test_13_upgrade_card(self):
        """TC-13: Улучшение карточки 0->1 звезда (3 повторки)"""
        self._reg_login()
        db=self._db(); uid=db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,4,0)",(uid,1)); db.commit(); db.close()
        rv=self.client.post('/upgrade_card/1'); d=json.loads(rv.data)
        self.assertEqual(d['star_level'],1)
        db=self._db(); uc=db.execute("SELECT * FROM user_card WHERE user_id=? AND card_id=1",(uid,)).fetchone(); db.close()
        self.assertEqual(uc['quantity'],1); self.assertEqual(uc['star_level'],1)

    def test_14_upgrade_no_dupes(self):
        """TC-14: Улучшение без повторок — ошибка"""
        self._reg_login()
        db=self._db(); uid=db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,2,0)",(uid,1)); db.commit(); db.close()
        rv=self.client.post('/upgrade_card/1')
        self.assertEqual(rv.status_code,400)

    def test_15_sell_duplicate(self):
        """TC-15: Продажа дубликата common — +25 монет"""
        self._reg_login()
        db=self._db(); uid=db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        before=db.execute("SELECT coins FROM user WHERE id=?",(uid,)).fetchone()['coins']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,3,0)",(uid,1)); db.commit(); db.close()
        rv=self.client.post('/sell_card/1'); d=json.loads(rv.data)
        self.assertTrue(d['sold']); self.assertEqual(d['price'],25)
        db=self._db(); after=db.execute("SELECT coins FROM user WHERE id=?",(uid,)).fetchone()['coins']; db.close()
        self.assertEqual(after,before+25)

    def test_16_sell_only_one(self):
        """TC-16: Продажа единственной — отказ"""
        self._reg_login()
        db=self._db(); uid=db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,1,0)",(uid,2)); db.commit(); db.close()
        rv=self.client.post('/sell_card/2'); self.assertEqual(rv.status_code,400)

    def test_17_wishlist_add(self):
        """TC-17: Добавление в wishlist"""
        self._reg_login()
        rv=self.client.post('/wishlist/toggle/1'); d=json.loads(rv.data)
        self.assertEqual(d['action'],'added')
        rv=self.client.get('/wishlist'); items=json.loads(rv.data)
        self.assertEqual(len(items),1)

    def test_18_wishlist_remove(self):
        """TC-18: Удаление из wishlist"""
        self._reg_login()
        self.client.post('/wishlist/toggle/1')
        rv=self.client.post('/wishlist/toggle/1'); d=json.loads(rv.data)
        self.assertEqual(d['action'],'removed')
        rv=self.client.get('/wishlist'); self.assertEqual(len(json.loads(rv.data)),0)

    def test_19_trade_create(self):
        """TC-19: Создание обмена"""
        self._reg('u1','u1@m.ru','p'); self._reg('u2','u2@m.ru','p'); self._login('u1','p')
        db=self._db()
        u1=db.execute("SELECT id FROM user WHERE username='u1'").fetchone()['id']
        u2=db.execute("SELECT id FROM user WHERE username='u2'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity)VALUES(?,?,1)",(u1,1))
        db.execute("INSERT INTO user_card(user_id,card_id,quantity)VALUES(?,?,1)",(u2,2)); db.commit(); db.close()
        rv=self.client.post('/trade/create',data={'to_user_id':str(u2),'offered_card_id':'1','requested_card_id':'2'})
        self.assertEqual(json.loads(rv.data)['status'],'pending')
        db=self._db(); t=db.execute("SELECT * FROM trade_offer WHERE from_user_id=?",(u1,)).fetchone(); db.close()
        self.assertIsNotNone(t); self.assertEqual(t['status'],'pending')

    def test_20_update_bio(self):
        """TC-20: Обновление bio"""
        self._reg_login()
        self.client.post('/profile/update',data={'bio':'Hello!'},follow_redirects=True)
        db=self._db(); bio=db.execute("SELECT bio FROM user WHERE username='testuser'").fetchone()['bio']; db.close()
        self.assertEqual(bio,'Hello!')

    def test_21_password_hash(self):
        """TC-21: Пароли хэшируются"""
        self._reg('h','h@t.ru','mypass')
        db=self._db(); pw=db.execute("SELECT password_hash FROM user WHERE username='h'").fetchone()['password_hash']; db.close()
        self.assertNotEqual(pw,'mypass')
        self.assertTrue(pw.startswith('scrypt:') or pw.startswith('pbkdf2:'))

    def test_22_reset_password(self):
        """TC-22: Сброс пароля — новый пароль работает"""
        self._reg('r','r@m.ru','old')
        rv=self.client.post('/reset-password',data={'username':'r','email':'r@m.ru',
            'new_password':'newp1234','confirm_password':'newp1234'})
        self.assertTrue(json.loads(rv.data)['success'])
        self._login('r','newp1234')
        with self.client.session_transaction() as s: self.assertIn('user_id',s)

    def test_23_reset_mismatch(self):
        """TC-23: Сброс — пароли не совпадают"""
        self._reg('r2','r2@m.ru','old')
        rv=self.client.post('/reset-password',data={'username':'r2','email':'r2@m.ru',
            'new_password':'a','confirm_password':'b'})
        self.assertEqual(rv.status_code,400)

    def test_24_collection(self):
        """TC-24: Коллекция отображает карточки"""
        self._reg_login()
        db=self._db(); uid=db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,2,0)",(uid,1))
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level)VALUES(?,?,1,3)",(uid,3)); db.commit(); db.close()
        rv=self.client.get('/collection'); d=json.loads(rv.data)
        self.assertEqual(len(d),2)
        self.assertEqual(next(c for c in d if c['card_id']==1)['quantity'],2)
        self.assertEqual(next(c for c in d if c['card_id']==3)['star_level'],3)

    def test_25_rating(self):
        """TC-25: Рейтинг по богатству"""
        self._reg('rich','ri@m.ru','p'); self._reg('poor','po@m.ru','p')
        db=self._db(); db.execute("UPDATE user SET coins=500 WHERE username='rich'")
        db.execute("UPDATE user SET coins=10 WHERE username='poor'")
        rid=db.execute("SELECT id FROM user WHERE username='rich'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity)VALUES(?,?,2)",(rid,4)); db.commit(); db.close()
        rv=self.client.get('/rating'); d=json.loads(rv.data)
        self.assertEqual(d[0]['username'],'rich'); self.assertGreater(d[0]['wealth'],d[1]['wealth'])

    def test_26_response_time(self):
        """TC-26: Время отклика < 2 сек"""
        self._reg_login()
        for ep in ['/profile','/collection','/wishlist','/rating']:
            t=time.time(); self.client.get(ep); el=time.time()-t
            self.assertLess(el,2.0,f"{ep}: {el:.3f}s")

    def test_27_auth_required(self):
        """TC-27: Защита маршрутов без авторизации"""
        for ep in ['/profile','/collection','/wishlist']:
            rv=self.client.get(ep,follow_redirects=False)
            self.assertEqual(rv.status_code,302); self.assertIn('/login',rv.headers.get('Location',''))
    
    def test_28_sql_injection_login(self):
        """TC-28: SQL injection в логине"""
        self._reg('safe','safe@m.ru','pass')
        self.client.post('/login', data={
            'username': "' OR 1=1 --",
            'password': 'anything'
        })
        with self.client.session_transaction() as s:
            self.assertNotIn('user_id', s)

    def test_29_sql_injection_register(self):
        """TC-29: SQL injection при регистрации"""
        self.client.post('/register', data={
            'username': "hacker'; DROP TABLE user; --",
            'email': 'hack@m.ru',
            'password': '1234'
        })
        db = self._db()
        users = db.execute("SELECT COUNT(*) as c FROM user").fetchone()['c']
        db.close()
        self.assertEqual(users, 1)  # таблица не сломалась

    def test_30_invalid_card_id_sell(self):
        """TC-30: Продажа несуществующей карты"""
        self._reg_login()
        rv = self.client.post('/sell_card/999')
        self.assertEqual(rv.status_code, 404)

    def test_31_invalid_card_id_upgrade(self):
        """TC-31: Апгрейд несуществующей карты"""
        self._reg_login()
        rv = self.client.post('/upgrade_card/999')
        self.assertEqual(rv.status_code, 404)

    def test_32_invalid_quiz_id(self):
        """TC-32: Несуществующий quiz"""
        self._reg_login()
        rv = self.client.post('/quiz/999')
        self.assertEqual(rv.status_code, 404)

    def test_33_bio_length_limit(self):
        """TC-33: Ограничение bio (400 символов)"""
        self._reg_login()
        long_bio = "a" * 1000
        self.client.post('/profile/update', data={'bio': long_bio})
        db = self._db()
        bio = db.execute("SELECT bio FROM user WHERE username='testuser'").fetchone()['bio']
        db.close()
        self.assertEqual(len(bio), 400)

    def test_34_open_pack_invalid_quantity(self):
        """TC-34: Неверное количество паков → дефолт 1"""
        self._reg_login()
        rv = self.client.post('/open-pack', data={'quantity': '999'})
        d = json.loads(rv.data)
        self.assertEqual(len(d['dropped']), 1)

    def test_35_double_sell(self):
        """TC-35: Повторная продажа карты"""
        self._reg_login()
        db = self._db()
        uid = db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity) VALUES(?,?,2)", (uid,1))
        db.commit(); db.close()

        self.client.post('/sell_card/1')
        rv = self.client.post('/sell_card/1')  # второй раз
        self.assertEqual(rv.status_code, 400)

    def test_36_upgrade_max_level(self):
        """TC-36: Апгрейд при максимальном уровне"""
        self._reg_login()
        db = self._db()
        uid = db.execute("SELECT id FROM user WHERE username='testuser'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity,star_level) VALUES(?,?,100,7)", (uid,1))
        db.commit(); db.close()

        rv = self.client.post('/upgrade_card/1')
        self.assertEqual(rv.status_code, 400)

    def test_37_cross_user_access(self):
        """TC-37: Попытка доступа к чужим данным"""
        self._reg('u1','u1@m.ru','p')
        self._reg('u2','u2@m.ru','p')

        self._login('u1','p')
        db = self._db()
        u2_id = db.execute("SELECT id FROM user WHERE username='u2'").fetchone()['id']
        db.execute("INSERT INTO user_card(user_id,card_id,quantity) VALUES(?,?,2)", (u2_id,1))
        db.commit(); db.close()

        # u1 пытается продать карту u2
        rv = self.client.post('/sell_card/1')
        self.assertIn(rv.status_code, [400,404])

if __name__=='__main__':
    loader=unittest.TestLoader(); suite=loader.loadTestsFromTestCase(TestMireaBratva)
    runner=unittest.TextTestRunner(verbosity=2); result=runner.run(suite)
    p=result.testsRun-len(result.failures)-len(result.errors)
    print(f"\n{'='*60}\n  ИТОГО: {result.testsRun} тестов\n  PASSED: {p}\n  FAILED: {len(result.failures)}\n  ERRORS: {len(result.errors)}\n{'='*60}")

