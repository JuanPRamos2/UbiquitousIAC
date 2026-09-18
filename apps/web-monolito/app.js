const path = require('path');
const express = require('express');
const session = require('express-session');
const methodOverride = require('method-override');
const dotenv = require('dotenv');

dotenv.config({ path: path.join(__dirname, '.env') });

const authRoutes = require('./routes/authRoutes');
const bookRoutes = require('./routes/bookRoutes');
const catalogRoutes = require('./routes/catalogRoutes');
const adminRoutes = require('./routes/adminRoutes');
const { requireAuth } = require('./middleware/auth');
const { flash } = require('./middleware/flash');
const { notFound, errorHandler } = require('./middleware/errors');
const bookService = require('./services/bookService');

const app = express();
const router = express.Router();
const BASE_PATH = process.env.BASE_PATH || '/library';
const HOST = process.env.HOST || '127.0.0.1';
const PORT = Number(process.env.PORT || 3000);

if (!process.env.SESSION_SECRET) {
  throw new Error('Falta SESSION_SECRET en el archivo .env');
}

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.set('trust proxy', 1);

app.use((req, res, next) => {
  res.locals.basePath = BASE_PATH;
  res.locals.u = (p = '/') => `${BASE_PATH}${p.startsWith('/') ? p : `/${p}`}`;
  res.locals.currentUser = null;
  res.locals.reqPath = req.path;
  next();
});

router.use(express.urlencoded({ extended: true }));
router.use(methodOverride('_method'));
router.use(
  session({
    name: 'library.sid',
    secret: process.env.SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      maxAge: 1000 * 60 * 60 * 8,
      httpOnly: true,
      sameSite: 'lax',
      path: BASE_PATH,
      secure: process.env.NODE_ENV === 'production'
    }
  })
);
router.use(flash);
router.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  next();
});
router.use(express.static(path.join(__dirname, 'public')));
router.use('/uploads', express.static(path.join(__dirname, 'uploads')));

router.get('/', requireAuth, async (req, res) => {
  let stats = { books: 0, categories: 0, authors: 0, users: 0 };
  try {
    stats = await bookService.getDashboardStats();
  } catch (error) {
    console.error(error.message);
  }
  res.render('dashboard/index', { title: 'Inicio', stats });
});

router.use('/', authRoutes);
router.use('/books', bookRoutes);
router.use('/catalogs', catalogRoutes);
router.use('/admin', adminRoutes);

router.get('/health', (req, res) => {
  res.type('text').send('OK');
});

router.use(notFound);
router.use(errorHandler);

app.use(BASE_PATH, router);
app.get('/', (req, res) => res.redirect(BASE_PATH));
app.use((req, res) => {
  res.status(404).type('text').send('Not found');
});

if (require.main === module) {
  app.listen(PORT, HOST, () => {
    console.log(`Librería escuchando en http://${HOST}:${PORT}${BASE_PATH}`);
  });
}

module.exports = app;
