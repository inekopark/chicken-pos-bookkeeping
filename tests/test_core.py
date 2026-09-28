import tempfile
import unittest
from pathlib import Path
from core import Store

class Flows(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.s=Store(Path(self.temp.name)/'shop.db')
        self.p=self.s.product('WHOLE','Whole chicken','kg','180','165')
        self.vendor=self.s.party('suppliers','Supplier')
        self.customer=self.s.party('customers','Restaurant')
        self.shift=self.s.open_shift('cashier','2000')

    def tearDown(self):
        self.s.db.close(); self.temp.cleanup()

    def test_purchase_sale_cash_credit_and_close(self):
        purchase=self.s.purchase(self.vendor,[(self.p,'10','120')],paid='200',method='CASH',shift=self.shift)
        self.assertEqual(self.s.stock(self.p),(10000,120000))
        self.s.pay_supplier(purchase,'100',method='BANK')
        sale=self.s.sale(self.shift,[(self.p,'2')])
        credit=self.s.sale(self.shift,[(self.p,'1')],method='CREDIT',customer=self.customer)
        self.s.collect(credit,'50',shift=self.shift)
        self.s.expense('Fuel','100',shift=self.shift)
        self.assertEqual(self.s.stock(self.p),(7000,84000))
        self.assertEqual(self.s.expected(self.shift),211000)
        close=self.s.close_shift(self.shift,'2100','1800','Owner')
        self.assertEqual(close['variance'],-1000)
        with self.assertRaises(ValueError): self.s.sale(self.shift,[(self.p,'1')])

    def test_failed_sale_rolls_back(self):
        self.s.purchase(self.vendor,[(self.p,'1','120')])
        with self.assertRaises(ValueError): self.s.sale(self.shift,[(self.p,'0.5'),(self.p,'0.6')])
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM sales').fetchone()[0],0)
        self.assertEqual(self.s.stock(self.p),(1000,12000))

if __name__=='__main__': unittest.main()
