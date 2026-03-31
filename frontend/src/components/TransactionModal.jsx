import React, { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Grid, MenuItem, Box,
  Typography, Alert, CircularProgress
} from '@mui/material';
import { Send, Shuffle } from '@mui/icons-material';
import axios from 'axios';

const MERCHANT_CATEGORIES = [
  'entertainment', 'food_dining', 'gas_transport', 'grocery_net',
  'grocery_pos', 'health_fitness', 'home', 'kids_pets',
  'misc_net', 'misc_pos', 'personal_care', 'shopping_net',
  'shopping_pos', 'travel', 'online_gambling', 'international_transfer'
];

const TransactionModal = ({ open, onClose, onTransactionCreated }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [formData, setFormData] = useState({
    id: `TXN${Math.floor(Math.random() * 1000000)}`,
    sender_account: 'ACC' + Math.floor(Math.random() * 10000),
    receiver_account: 'ACC' + Math.floor(Math.random() * 10000),
    amount: 100.0,
    timestamp: new Date().toISOString(),
    merchant_category: 'food_dining',
    velocity_1min: 1,
    velocity_5min: 1,
    velocity_1hr: 1,
    haversine_distance: 5.2,
    hour: new Date().getHours(),
    day_of_week: new Date().getDay(),
    is_holiday: false
  });

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : (type === 'number' ? parseFloat(value) : value)
    }));
  };

  const handleRandomize = () => {
    setFormData({
      ...formData,
      id: `TXN${Math.floor(Math.random() * 1000000)}`,
      amount: parseFloat((Math.random() * 5000).toFixed(2)),
      merchant_category: MERCHANT_CATEGORIES[Math.floor(Math.random() * MERCHANT_CATEGORIES.length)],
      haversine_distance: parseFloat((Math.random() * 1000).toFixed(2)),
      hour: Math.floor(Math.random() * 24),
      day_of_week: Math.floor(Math.random() * 7),
      velocity_1min: Math.floor(Math.random() * 5),
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Use the new public simulation endpoint
      const response = await axios.post('/api/transactions/simulate', formData);
      setSuccess(response.data);
      if (onTransactionCreated) {
        onTransactionCreated(response.data);
      }
      // Keep open for a bit to show success, then close
      setTimeout(() => {
        onClose();
        setSuccess(null);
      }, 2000);
    } catch (err) {
      console.error('Error creating transaction:', err);
      setError(err.response?.data?.detail || 'Failed to create transaction');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ bgcolor: 'primary.main', color: 'white' }}>
        Create New Transaction
      </DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ mt: 2 }}>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && (
            <Alert severity={success.final_fraud_probability > 0.5 ? "warning" : "success"} sx={{ mb: 2 }}>
              Transaction Processed! Risk: {success.risk_level} ({Math.round(success.final_fraud_probability * 100)}%)
            </Alert>
          )}

          <Grid container spacing={2}>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Transaction ID" name="id"
                value={formData.id} onChange={handleChange} required
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Amount ($)" name="amount" type="number"
                value={formData.amount} onChange={handleChange} required
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Sender Account" name="sender_account"
                value={formData.sender_account} onChange={handleChange} required
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Receiver Account" name="receiver_account"
                value={formData.receiver_account} onChange={handleChange} required
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                fullWidth select label="Merchant Category" name="merchant_category"
                value={formData.merchant_category} onChange={handleChange}
              >
                {MERCHANT_CATEGORIES.map(cat => (
                  <MenuItem key={cat} value={cat}>{cat}</MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Distance (km)" name="haversine_distance" type="number"
                value={formData.haversine_distance} onChange={handleChange}
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                fullWidth label="Hour (0-23)" name="hour" type="number"
                value={formData.hour} onChange={handleChange}
              />
            </Grid>
          </Grid>

          <Box sx={{ mt: 3, p: 2, bgcolor: 'background.paper', borderRadius: 1, border: '1px dashed grey' }}>
            <Typography variant="caption" color="text.secondary">
              Simulation Tip: Try "online_gambling" with a high amount or "international_transfer" with a distance &gt; 1000km to see the high-risk detection in action!
            </Typography>
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={handleRandomize} startIcon={<Shuffle />} loading={loading}>
            Randomize
          </Button>
          <Box sx={{ flexGrow: 1 }} />
          <Button onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            startIcon={loading ? <CircularProgress size={20} /> : <Send />}
            disabled={loading}
          >
            Send Transaction
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default TransactionModal;
