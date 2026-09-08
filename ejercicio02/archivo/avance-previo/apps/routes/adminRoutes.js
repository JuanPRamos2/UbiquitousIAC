const express = require('express');
const router = express.Router();
const { listUsers, updateUserRole, deleteUser } = require('../models/userModel');

const requireAdmin = (req, res, next) => {
  if (!req.session.user || req.session.user.role !== 'admin') {
    return res.status(403).render('error/403', { title: 'Acceso denegado' });
  }
  next();
};

router.use(requireAdmin);

router.get('/users', async (req, res) => {
  const users = await listUsers();
  res.render('users/admin', { title: 'Administración de usuarios', users });
});

router.post('/users/:id/role', async (req, res) => {
  await updateUserRole(req.params.id, req.body.role);
  res.redirect('/admin/users');
});

router.post('/users/:id/delete', async (req, res) => {
  await deleteUser(req.params.id);
  res.redirect('/admin/users');
});

module.exports = router;
