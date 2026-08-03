import csv
import json
import logging
from datetime import datetime
from django.core.management.base import BaseCommand
from core.tasks import process_return_prime_webhook

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Imports historical Return Prime data from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the Return Prime export CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        try:
            with open(csv_file_path, mode='r', encoding='utf-8-sig') as file:
                reader = csv.DictReader(file)
                
                success_count = 0
                fail_count = 0
                
                for row in reader:
                    serial_number = row.get('serial_number', '').strip()
                    if not serial_number:
                        continue
                        
                    request_type = row.get('type', '').strip().upper()
                    if request_type not in ['RETURN', 'EXCHANGE']:
                        request_type = 'RETURN'

                    status = row.get('status', 'APPROVED').strip().upper()
                    order_number = row.get('order_number', '').strip()
                    order_id = row.get('order_id', '').strip()
                    
                    # Convert amounts to float safely
                    def parse_float(val):
                        try:
                            return float(str(val).replace(',', '').strip()) if val else 0.0
                        except ValueError:
                            return 0.0

                    item_price = parse_float(row.get('item_price'))
                    item_quantity = int(parse_float(row.get('item_quantity', 1)) or 1)
                    incentive = parse_float(row.get('incentive_amount'))
                    return_fee = parse_float(row.get('return_fee'))
                    
                    # Construct synthetic payload mimicking Return Prime JSON
                    payload = {
                        "request": {
                            "id": serial_number,
                            "request_number": serial_number,
                            "request_type": request_type,
                            "status": status,
                            "order": {
                                "name": order_number,
                                "id": order_id
                            },
                            "customer": {
                                "name": row.get('customer_name', '').strip(),
                                "email": row.get('customer_email', '').strip(),
                                "phone": row.get('customer_phone', '').strip(),
                                "address": row.get('customer_address', '').strip()
                            },
                            "tracking_number": row.get('pickup_awb', '').strip(),
                            "logistic_partner": row.get('pickup_logistics', '').strip(),
                            "incentive": incentive,
                            "line_items": [
                                {
                                    "quantity": item_quantity,
                                    "reason": row.get('reason', '').strip(),
                                    "notes": row.get('customer_comment', '').strip(),
                                    "original_product": {
                                        "title": row.get('item_name', '').strip(),
                                        "sku": row.get('sku', '').strip(),
                                        "price": item_price
                                    },
                                    "exchange_product": {
                                        "title": row.get('exchange_with', '').strip(),
                                        "sku": row.get('exchange_with_sku', '').strip(),
                                        "price": parse_float(row.get('exchange_with_amount'))
                                    } if row.get('exchange_with', '').strip() else None,
                                    "shop_price": {
                                        "actual_amount": item_price,
                                        "total_tax": 0.0,
                                        "total_discount": 0.0
                                    },
                                    "return_fee": {
                                        "price_set": {
                                            "shop_money": {
                                                "amount": return_fee
                                            }
                                        }
                                    },
                                    "exchange_fee": {
                                        "price_set": {
                                            "shop_money": {
                                                "amount": return_fee # In the CSV, exchange fees usually just sit under "return_fee" or exchange_with_amount
                                            }
                                        }
                                    },
                                    "shipping": [
                                        {
                                            "awb": row.get('pickup_awb', '').strip(),
                                            "shipping_company": row.get('pickup_logistics', '').strip()
                                        }
                                    ]
                                }
                            ]
                        }
                    }

                    # Feed it through the existing webhook pipeline
                    try:
                        result = process_return_prime_webhook(payload)
                        if "Failed" not in str(result):
                            success_count += 1
                        else:
                            fail_count += 1
                            self.stdout.write(self.style.WARNING(f"Warning importing {serial_number}: {result}"))
                    except Exception as e:
                        fail_count += 1
                        self.stdout.write(self.style.ERROR(f"Error importing {serial_number}: {str(e)}"))

                self.stdout.write(self.style.SUCCESS(f"Finished parsing CSV. Successfully synced: {success_count}, Failed: {fail_count}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error reading CSV file: {str(e)}"))
