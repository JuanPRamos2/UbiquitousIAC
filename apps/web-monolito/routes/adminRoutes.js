const express = require('express');
const router = express.Router();
const { requireAdmin } = require('../middleware/auth');
const { setNotice, setError } = require('../middleware/flash');
const { friendlyDbError } = require('../services/dbErrors');
const authService = require('../services/authService');

router.use(requireAdmin);

router.get('/users', async (req, res, next) => {
  try {
    const users = await authService.listUsers();
    res.render('users/admin', { title: 'Administración de usuarios', users });
  } catch (error) {
    next(error);
  }
});

router.post('/users/:id/role', async (req, res) => {
  try {
    await authService.updateUserRole(req.params.id, req.body.role);
    setNotice(req, 'Rol actualizado.');
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/admin/users`);
});

router.post('/users/:id/delete', async (req, res) => {
  try {
    if (String(req.session.user.id) === String(req.params.id)) {
      setError(req, 'No puede eliminar su propia cuenta mientras está autenticado.');
    } else {
      await authService.deleteUser(req.params.id);
      setNotice(req, 'Usuario eliminado.');
    }
  } catch (error) {
    setError(req, friendlyDbError(error));
  }
  res.redirect(`${res.locals.basePath}/admin/users`);
});

module.exports = router;
