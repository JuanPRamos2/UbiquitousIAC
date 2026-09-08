const express = require('express');
const session = require('express-session');
const methodOverride = require('method-override');
const path = require('path');
const dotenv = require('dotenv');

const authRoutes = require('./routes/authRoutes');
const bookRoutes = require('./routes/bookRoutes');
const catalogRoutes = require('./routes/catalogRoutes');
const adminRoutes = require('./routes/adminRoutes');
const { getDashboardStats } = require('./models/bookModel');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, 'public')));
app.use('/services', express.static(path.join(__dirname, 'services')));
app.use(methodOverride('_method'));
app.use(
  session({
    secret: process.env.SESSION_SECRET || 'library-secret-key',
    resave: false,
    saveUninitialized: false,
    cookie: { maxAge: 1000 * 60 * 60 * 8 }
  })
);

app.use((req, res, next) => {
  res.locals.currentUser = req.session.user || null;
  res.locals.reqPath = req.path;
  next();
});

app.get('/', async (req, res) => {
  if (!req.session.user) {
    return res.redirect('/login');
  }

  try {
    const stats = await getDashboardStats();
    res.render('dashboard/index', { title: 'Dashboard', stats });
  } catch (error) {
    console.error(error);
    res.status(500).render('dashboard/index', {
      title: 'Dashboard',
      stats: { books: 0, categories: 0, authors: 0, users: 0 },
      error: 'No se pudo cargar el dashboard.'
    });
  }
});

app.use('/', authRoutes);
app.use('/books', bookRoutes);
app.use('/catalogs', catalogRoutes);
app.use('/admin', adminRoutes);

app.get('/health', (req, res) => {
  res.send('OK');
});

app.use((req, res) => {
  res.status(404).render('error/404', { title: 'Página no encontrada' });
});

app.listen(PORT, () => {
  console.log(`Servidor de la librería escuchando en http://localhost:${PORT}`);
});

module.exports = app;
