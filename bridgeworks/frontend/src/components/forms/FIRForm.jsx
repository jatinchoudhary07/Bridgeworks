import React, { useState, useEffect } from 'react';
import {
  Box, TextField, Button, Typography, MenuItem, Paper, Alert, CircularProgress, Divider, Chip
} from '@mui/material';
import DescriptionIcon from '@mui/icons-material/Description';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

import { BACKEND_URL } from '../../config/api';
import { apiClient } from "../../apiClient";

export default function FIRForm() {
  const [formData, setFormData] = useState({
    orderNumber: '',
    issueType: '',
    platform: '',
    subject: '',
    description: '',
  });

  const [files, setFiles] = useState([]);
  const [orderDetails, setOrderDetails] = useState(null);
  const [orderLoading, setOrderLoading] = useState(false);
  const [message, setMessage] = useState({ text: '', severity: 'info' });
  const [submitting, setSubmitting] = useState(false);

  const issueTypes = [
    { value: 'DELIVERY', label: 'Delivery/Tracking Issue' },
    { value: 'RTO', label: 'RTO Dispute' },
    { value: 'DAMAGE', label: 'Product Damage/Quality' },
    { value: 'MISSING', label: 'Missing Item/Order' },
    { value: 'REFUND', label: 'Refund/Payment Issue' },
    { value: 'CANCELLATION', label: 'Cancellation Request' },
    { value: 'OTHER', label: 'Other' },
  ];

  const platforms = [
    { value: 'EMAIL', label: 'Email' },
    { value: 'WHATSAPP', label: 'Whatsapp' },
    { value: 'CALL', label: 'Call' },
    { value: 'INSTAGRAM', label: 'Instagram' },
    { value: 'FACEBOOK', label: 'Facebook' },
    { value: 'OTHER', label: 'Other' },
  ];

  // Fetch order details when order number changes
  useEffect(() => {
    const fetchOrderDetails = async () => {
      if (formData.orderNumber && formData.orderNumber.length >= 3) {
        setOrderLoading(true);
        try {
          const response = await apiClient(
            `${BACKEND_URL}/api/orders/lookup/?order_number=${encodeURIComponent(formData.orderNumber)}`,
            { credentials: 'include' }
          );

          if (response.ok) {
            const data = await response.json();
            // Handle different response formats
            if (Array.isArray(data) && data.length > 0) {
              setOrderDetails(data[0]);
            } else if (data && !Array.isArray(data) && (data.order_number || data.id)) {
              setOrderDetails(data);
            } else if (data && data.results && data.results.length > 0) {
              setOrderDetails(data.results[0]);
            } else {
              setOrderDetails(null);
            }
          } else {
            setOrderDetails(null);
          }
        } catch (error) {
          console.error('Error fetching order:', error);
          setOrderDetails(null);
        } finally {
          setOrderLoading(false);
        }
      } else {
        setOrderDetails(null);
      }
    };

    const debounce = setTimeout(() => {
      fetchOrderDetails();
    }, 500);

    return () => clearTimeout(debounce);
  }, [formData.orderNumber]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (e) => {
    setFiles(Array.from(e.target.files));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.orderNumber || !formData.issueType || !formData.platform || !formData.subject || !formData.description) {
      setMessage({ text: 'Please fill all required fields', severity: 'error' });
      return;
    }

    setSubmitting(true);
    setMessage({ text: '', severity: 'info' });

    try {
      const formDataToSend = new FormData();

      // Use the exact field names expected by your Django backend
      formDataToSend.append('order_number', formData.orderNumber);
      formDataToSend.append('issue_type', formData.issueType);
      formDataToSend.append('first_place_of_contact', formData.platform);
      formDataToSend.append('subject', formData.subject);
      formDataToSend.append('description', formData.description);

      // Append files - backend expects 'images' field
      files.forEach((file) => {
        formDataToSend.append('images', file, file.name);
      });

      console.log('Submitting data:'); // Debug log
      console.log('Form data:', {
        order_number: formData.orderNumber,
        issue_type: formData.issueType,
        first_place_of_contact: formData.platform,
        subject: formData.subject,
        description: formData.description,
        files_count: files.length
      });

      const response = await apiClient(`${BACKEND_URL}/api/cases/`, {
        method: 'POST',
        headers: {

        },
        credentials: 'include',
        body: formDataToSend,
      });

      const responseData = await response.json();
      console.log('Response:', responseData); // Debug log

      if (response.ok) {
        setMessage({
          text: `FIR created successfully! Case Number: ${responseData.case_number || responseData.id}`,
          severity: 'success'
        });

        // Reset form
        setFormData({
          orderNumber: '',
          issueType: '',
          platform: '',
          subject: '',
          description: '',
        });
        setFiles([]);
        setOrderDetails(null);
      } else {
        // Better error handling
        console.error('Error response:', responseData);
        let errorMsg = 'Failed to create FIR';

        if (responseData.order_number) {
          errorMsg = Array.isArray(responseData.order_number)
            ? responseData.order_number[0]
            : responseData.order_number;
        } else if (responseData.issue_type) {
          errorMsg = Array.isArray(responseData.issue_type)
            ? responseData.issue_type[0]
            : responseData.issue_type;
        } else if (responseData.first_place_of_contact) {
          errorMsg = Array.isArray(responseData.first_place_of_contact)
            ? responseData.first_place_of_contact[0]
            : responseData.first_place_of_contact;
        } else if (responseData.detail) {
          errorMsg = responseData.detail;
        } else if (responseData.non_field_errors) {
          errorMsg = Array.isArray(responseData.non_field_errors)
            ? responseData.non_field_errors[0]
            : responseData.non_field_errors;
        }

        throw new Error(errorMsg);
      }
    } catch (error) {
      console.error('Submit error:', error);
      setMessage({ text: error.message || 'Failed to create FIR', severity: 'error' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', gap: 1, height: '100%', overflow: 'hidden' }}>
      {/* Left Side - FIR Form (65%) */}
      <Paper
        elevation={2}
        sx={{
          flex: '0 0 65%',
          p: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <DescriptionIcon color="error" fontSize="medium" />
          <Typography variant="h6" fontWeight="bold">
            First Information Report (FIR)
          </Typography>
        </Box>

        {message.text && (
          <Alert
            severity={message.severity}
            sx={{ mb: 2 }}
            onClose={() => setMessage({ text: '', severity: 'info' })}
          >
            {message.text}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Order Number */}
          <TextField
            label="Order Number"
            name="orderNumber"
            value={formData.orderNumber}
            onChange={handleChange}
            required
            placeholder="Enter order number"
            size="small"
            sx={{ maxWidth: '300px' }}
            InputProps={{
              endAdornment: orderLoading && <CircularProgress size={16} />
            }}
          />

          {/* Report Details Section */}
          <Box>
            <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ mb: 1.5 }}>
              Report Details
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              <TextField
                select
                label="Issue Type"
                name="issueType"
                value={formData.issueType}
                onChange={handleChange}
                required
                size="small"
              >
                {issueTypes.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </TextField>

              <TextField
                select
                label="First Place of Contact"
                name="platform"
                value={formData.platform}
                onChange={handleChange}
                required
                size="small"
              >
                {platforms.map((platform) => (
                  <MenuItem key={platform.value} value={platform.value}>
                    {platform.label}
                  </MenuItem>
                ))}
              </TextField>
            </Box>
          </Box>

          {/* Subject */}
          <TextField
            fullWidth
            label="Subject"
            name="subject"
            value={formData.subject}
            onChange={handleChange}
            required
            placeholder="Brief summary of the issue"
            size="small"
          />

          {/* Description */}
          <TextField
            fullWidth
            label="Detailed Report/Description"
            name="description"
            value={formData.description}
            onChange={handleChange}
            required
            multiline
            rows={4}
            placeholder="Provide detailed information about the issue..."
            size="small"
          />

          {/* File Upload */}
          <Box>
            <Typography variant="caption" fontWeight="bold" display="block" gutterBottom>
              Attach Evidence (Optional)
            </Typography>
            <Button
              variant="outlined"
              component="label"
              startIcon={<CloudUploadIcon />}
              size="small"
              sx={{ py: 1 }}
            >
              Select Files
              <input
                type="file"
                hidden
                multiple
                onChange={handleFileChange}
                accept="image/*,video/*"
              />
            </Button>
            {files.length > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                {files.length} file(s) selected
              </Typography>
            )}
          </Box>

          {/* Submit Button */}
          <Button
            type="submit"
            variant="contained"
            size="medium"
            disabled={submitting || !orderDetails}
            sx={{
              py: 1.2,
              fontWeight: 'bold',
              mt: 1
            }}
          >
            {submitting ? <CircularProgress size={20} /> : 'FILE CASE (CREATE NEW CASE FILE)'}
          </Button>
        </Box>
      </Paper>

      {/* Right Side - Order Details (35%) */}
      <Paper
        elevation={2}
        sx={{
          flex: '0 0 35%',
          p: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
          bgcolor: 'background.default'
        }}
      >
        <Typography variant="h6" fontWeight="bold" gutterBottom>
          Order Details
        </Typography>
        <Divider sx={{ mb: 2 }} />

        {orderLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', py: 4 }}>
            <CircularProgress size={30} />
          </Box>
        ) : orderDetails ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Alert severity="success" icon={<CheckCircleIcon fontSize="small" />} sx={{ py: 0.5 }}>
              <Typography variant="body2" fontWeight="medium">Order Found</Typography>
            </Alert>

            <Box sx={{ p: 1.5, bgcolor: 'background.paper', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                <strong>Customer:</strong> {orderDetails.fir_customer_name || `${orderDetails.customer_first_name || ''} ${orderDetails.customer_last_name || ''}`.trim() || 'N/A'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                <strong>Phone:</strong> {orderDetails.contact_phone || 'N/A'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                <strong>Email:</strong> {orderDetails.contact_email || 'N/A'}
              </Typography>
              <Typography variant="body2" sx={{ mb: 0.5 }}>
                <strong>Total:</strong> <span style={{ color: '#0284c7', fontWeight: 600 }}>₹{orderDetails.total_price || orderDetails.total?.toFixed(2) || '0.00'}</span>
              </Typography>
              <Typography variant="body2" component="div">
                <strong>Status:</strong>{' '}
                <Chip
                  label={orderDetails.internal_fulfillment_status || orderDetails.status || 'Pending'}
                  variant="outlined"
                  size="small"
                  sx={{ height: '20px', fontSize: '0.7rem' }}
                />
              </Typography>
            </Box>

            {orderDetails.line_items && orderDetails.line_items.length > 0 && (
              <Box>
                <Typography variant="subtitle2" fontWeight="bold" gutterBottom sx={{ mb: 1 }}>
                  Line Items
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {orderDetails.line_items.map((item, index) => (
                    <Box
                      key={index}
                      sx={{
                        p: 1,
                        bgcolor: 'background.paper',
                        borderRadius: 1,
                        border: '1px solid',
                        borderColor: 'divider'
                      }}
                    >
                      <Typography variant="body2" fontWeight="600" sx={{ mb: 0.3 }}>
                        {item.title || item.product_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        SKU: {item.sku} | Qty: {item.quantity}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        ) : formData.orderNumber ? (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              No order found with this number
            </Typography>
          </Box>
        ) : (
          <Box sx={{ textAlign: 'center', py: 4 }}>
            <Typography variant="body2" color="text.secondary">
              Enter an order number to view details
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
}