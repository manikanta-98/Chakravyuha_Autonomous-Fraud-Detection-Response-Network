import React, { useState, useEffect } from 'react';
import {
  Grid, Card, CardContent, Typography, Box,
  LinearProgress, Chip, IconButton, Tooltip, Button
} from '@mui/material';
import {
  Security, TrendingUp, AccessTime, CheckCircle,
  Error, Warning, Refresh
} from '@mui/icons-material';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import axios from 'axios';
import { useWebSocketContext } from '../hooks/useWebSocket';
import TransactionModal from './TransactionModal';

const COLORS = ['#00ff88', '#ff4081', '#00aaff', '#ffaa00'];

const Dashboard = () => {
  const [metrics, setMetrics] = useState({
    total_transactions: 0,
    fraud_detected: 0,
    false_positives: 0,
    average_latency_ms: 0,
    uptime_percentage: 0,
    model_accuracy: 0
  });
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [recentTransactions, setRecentTransactions] = useState([]);
  const { transactionUpdates, agentStatus, isConnected } = useWebSocketContext();

  useEffect(() => {
    fetchMetrics();
    fetchRecentTransactions();
    const interval = setInterval(() => {
      fetchMetrics();
      fetchRecentTransactions();
    }, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await axios.get('/api/analytics/summary');
      setMetrics(response.data);
    } catch (error) {
      console.error('Error fetching metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchRecentTransactions = async () => {
    try {
      const response = await axios.get('/api/transactions/recent');
      setRecentTransactions(response.data);
    } catch (error) {
      console.error('Error fetching recent transactions:', error);
    }
  };

  const refreshMetrics = () => {
    setLoading(true);
    fetchMetrics();
  };

  const handleTransactionCreated = (newTx) => {
    // Optionally trigger a silent metrics refresh or update metrics locally
    fetchMetrics(); 
  };

  // Mock data for charts
  const latencyData = [
    { time: '00:00', latency: 45 },
    { time: '04:00', latency: 42 },
    { time: '08:00', latency: 48 },
    { time: '12:00', latency: 52 },
    { time: '16:00', latency: 47 },
    { time: '20:00', latency: 44 },
  ];

  const riskDistribution = [
    { name: 'Low Risk', value: 75, color: '#00ff88' },
    { name: 'Medium Risk', value: 20, color: '#ffaa00' },
    { name: 'High Risk', value: 5, color: '#ff4081' },
  ];

  if (loading) {
    return (
      <Box sx={{ width: '100%', mt: 2 }}>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
          Fraud Detection Dashboard
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            icon={isConnected ? <CheckCircle /> : <Error />}
            label={isConnected ? "Connected" : "Disconnected"}
            color={isConnected ? "success" : "error"}
            variant="outlined"
          />
          <Button
            variant="contained"
            color="secondary"
            startIcon={<Security />}
            onClick={() => setModalOpen(true)}
            sx={{ fontWeight: 'bold' }}
          >
            New Transaction
          </Button>
          <Tooltip title="Refresh Metrics">
            <IconButton onClick={refreshMetrics} color="primary">
              <Refresh />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Grid container spacing={3}>
        {/* Key Metrics Cards */}
        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Security sx={{ mr: 1, color: 'primary.main' }} />
                <Typography variant="h6">Total Transactions</Typography>
              </Box>
              <Typography variant="h4" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                {metrics.total_transactions.toLocaleString()}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Last 24 hours
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <Error sx={{ mr: 1, color: 'error.main' }} />
                <Typography variant="h6">Fraud Detected</Typography>
              </Box>
              <Typography variant="h4" sx={{ color: 'error.main', fontWeight: 'bold' }}>
                {metrics.fraud_detected.toLocaleString()}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {((metrics.fraud_detected / metrics.total_transactions) * 100).toFixed(1)}% of total
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <AccessTime sx={{ mr: 1, color: 'warning.main' }} />
                <Typography variant="h6">Avg Latency</Typography>
              </Box>
              <Typography variant="h4" sx={{ color: 'warning.main', fontWeight: 'bold' }}>
                {metrics.average_latency_ms.toFixed(1)}ms
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Target: &lt;300ms
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                <TrendingUp sx={{ mr: 1, color: 'success.main' }} />
                <Typography variant="h6">Uptime</Typography>
              </Box>
              <Typography variant="h4" sx={{ color: 'success.main', fontWeight: 'bold' }}>
                {metrics.uptime_percentage.toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Target: 99.9%
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Charts */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Latency Over Time
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={latencyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                  <XAxis dataKey="time" stroke="#ccc" />
                  <YAxis stroke="#ccc" />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: '4px'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="#00ff88"
                    strokeWidth={2}
                    dot={{ fill: '#00ff88' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Risk Distribution
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={riskDistribution}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  >
                    {riskDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: '#1a1a1a',
                      border: '1px solid #333',
                      borderRadius: '4px'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        {/* Recent Transactions */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent High-Risk Transactions
              </Typography>
              <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
                {(() => {
                  const combined = [
                    ...transactionUpdates,
                    ...recentTransactions.filter(rt => !transactionUpdates.find(ut => ut.transaction_id === rt.transaction_id))
                  ];
                  return combined.slice(0, 10).map((update, index) => (
                    <Box
                      key={index}
                    sx={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      p: 1,
                      borderBottom: '1px solid #333',
                      '&:last-child': { borderBottom: 'none' }
                    }}
                  >
                    <Box>
                      <Typography variant="body2">
                        Transaction {update.transaction_id}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        ${update.amount || 'N/A'} • {update.risk_level}
                      </Typography>
                    </Box>
                    <Chip
                      size="small"
                      label={`${(update.final_fraud_probability * 100).toFixed(1)}%`}
                      color={update.final_fraud_probability > 0.7 ? "error" : update.final_fraud_probability > 0.3 ? "warning" : "success"}
                    />
                  </Box>
                ))})()}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <TransactionModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onTransactionCreated={handleTransactionCreated}
      />
    </Box>
  );
};

export default Dashboard;