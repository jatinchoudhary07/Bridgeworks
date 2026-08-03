// src/PicklistModal.jsx

import React, { useMemo } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from "@mui/material";

export const PicklistModal = ({ open, onClose, orders }) => {

  // This is the core logic. It aggregates all line items from all orders.
  const aggregatedItems = useMemo(() => {
    if (!orders || orders.length === 0) {
      return [];
    }

    // Use a map to store items by SKU for easy aggregation
    const productMap = new Map();

    // Loop through each order and each line item in that order
    orders.forEach(order => {
      (order.line_items || []).forEach(item => {
        const sku = item.sku || "N/A";
        if (productMap.has(sku)) {
          // If we've seen this SKU before, just add the quantity
          productMap.get(sku).totalQuantity += item.quantity;
        } else {
          // If it's a new SKU, add it to our map
          productMap.set(sku, {
            sku: sku,
            title: item.title || item.name || "No Title",
            totalQuantity: item.quantity,
          });
        }
      });
    });

    // Convert the map back to an array and sort it by SKU
    return Array.from(productMap.values()).sort((a, b) => {
      const skuA = a.sku || "";
      const skuB = b.sku || "";
      return skuA.localeCompare(skuB);
    });
  }, [orders]);

  const handlePrint = () => {
    window.print();
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>Daily Picklist</DialogTitle>
      <DialogContent>
        <TableContainer component={Paper}>
          <Table stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 'bold' }}>SKU</TableCell>
                <TableCell sx={{ fontWeight: 'bold' }}>Product Title</TableCell>
                <TableCell align="right" sx={{ fontWeight: 'bold' }}>Total Quantity to Pick</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {aggregatedItems.map((item) => (
                <TableRow key={item.sku}>
                  <TableCell>{item.sku}</TableCell>
                  <TableCell>{item.title}</TableCell>
                  <TableCell align="right">{item.totalQuantity}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </DialogContent>
      <DialogActions>
        <Button onClick={handlePrint} variant="contained">Print</Button>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};