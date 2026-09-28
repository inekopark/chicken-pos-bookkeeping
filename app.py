"""Small Tkinter operator console for the first prototype."""
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from core import Store

store = Store(Path.home() / 'ChickenPOS' / 'shop.sqlite3')
root = tk.Tk()
root.title('Chicken POS — Prototype')
root.geometry('720x590')
shift = tk.StringVar(value='')
status = tk.StringVar(value='Open a shift to begin')

frame = ttk.Frame(root, padding=16)
frame.pack(fill='both', expand=True)
ttk.Label(frame, text='Chicken POS | Operator Console', font=('Arial', 17, 'bold')).pack(anchor='w')
ttk.Label(frame, textvariable=status).pack(anchor='w', pady=8)

def form(title, fields, action):
    win=tk.Toplevel(root); win.title(title); win.transient(root); win.grab_set()
    inputs={}
    for i,(key,default) in enumerate(fields):
        ttk.Label(win,text=key).grid(row=i,column=0,padx=10,pady=6,sticky='w')
        e=ttk.Entry(win,width=35); e.insert(0,default); e.grid(row=i,column=1,padx=10,pady=6)
        inputs[key]=e
    def submit():
        try:
            result=action({k:e.get().strip() for k,e in inputs.items()})
            status.set(str(result)); win.destroy(); refresh()
        except Exception as ex: messagebox.showerror('Could not save',str(ex),parent=win)
    ttk.Button(win,text='Save',command=submit).grid(row=len(fields),column=1,pady=12)

def refresh():
    for child in listing.get_children(): listing.delete(child)
    for p in store.db.execute('SELECT * FROM products ORDER BY name'):
        q,v=store.stock(p['id'])
        listing.insert('', 'end',values=(p['id'],p['name'],p['unit'],f'{q/1000:.3f}',f'{v/100:.2f}',f'{p["retail_cents"]/100:.2f}'))

def open_shift():
    def save(v):
        sid=store.open_shift(v['Cashier'],v['Opening cash (PHP)']); shift.set(str(sid)); return f'Shift #{sid} open'
    form('Open shift',[('Cashier','cashier'),('Opening cash (PHP)','2000')],save)

def sale():
    def save(v):
        sid=store.sale(int(shift.get()),[(int(v['Product ID']),v['Quantity'])],v['Sale type'].upper(),v['Payment'].upper(),int(v['Customer ID']) if v['Customer ID'] else None)
        return f'Sale #{sid} saved'
    form('Sale',[('Product ID',''),('Quantity','1'),('Sale type','RETAIL'),('Payment','CASH'),('Customer ID','')],save)

def purchase():
    def save(v):
        sid=store.purchase(int(v['Supplier ID']),[(int(v['Product ID']),v['Quantity'],v['Cost per unit (PHP)'])],v['Paid now (PHP)'],v['Payment'].upper(),int(shift.get()) if shift.get() and v['Payment'].upper()=='CASH' else None)
        return f'Purchase #{sid} saved'
    form('Delivery',[('Supplier ID',''),('Product ID',''),('Quantity','1'),('Cost per unit (PHP)',''),('Paid now (PHP)','0'),('Payment','BANK')],save)

def expense():
    def save(v):
        sid=store.expense(v['Category'],v['Amount (PHP)'],v['Payment'].upper(),int(shift.get()) if shift.get() and v['Payment'].upper()=='CASH' else None,v['Payee'])
        return f'Expense #{sid} saved'
    form('Expense',[('Category','Utilities'),('Amount (PHP)',''),('Payment','CASH'),('Payee','')],save)

def close():
    def save(v):
        result=store.close_shift(int(shift.get()),v['Cash counted (PHP)'],v['Remitted (PHP)'],v['Received by'])
        shift.set(''); return f'Closed. Expected ₱{result["expected"]/100:.2f}; variance ₱{result["variance"]/100:.2f}'
    if not shift.get(): messagebox.showerror('Shift','Open a shift first'); return
    form('Close shift',[('Cash counted (PHP)',''),('Remitted (PHP)',''),('Received by','')],save)

def add_product():
    def save(v):
        product_id = store.product(v['SKU'], v['Name'], v['Unit'], v['Retail PHP'], v['Wholesale PHP'])
        return f'Product #{product_id} saved'
    form('Product', [('SKU',''), ('Name',''), ('Unit','kg'),
                     ('Retail PHP',''), ('Wholesale PHP','')], save)

def add_supplier():
    form('Supplier', [('Name','')],
         lambda v: f'Supplier #{store.party("suppliers", v["Name"])} saved')

def add_customer():
    form('Customer', [('Name','')],
         lambda v: f'Customer #{store.party("customers", v["Name"])} saved')

buttons=ttk.Frame(frame); buttons.pack(fill='x',pady=10)
actions = [
    ('Add product', add_product), ('Add supplier', add_supplier),
    ('Add customer', add_customer), ('Open shift', open_shift),
    ('Sale', sale), ('Delivery', purchase), ('Expense', expense),
    ('Close shift', close),
]
for label,cmd in actions:
    ttk.Button(buttons,text=label,command=cmd).pack(side='left',padx=2,pady=3)
listing=ttk.Treeview(frame,columns=('ID','Product','Unit','Stock','Value PHP','Retail PHP'),show='headings',height=15)
for col in listing['columns']: listing.heading(col,text=col); listing.column(col,width=100)
listing.pack(fill='both',expand=True)
ttk.Label(frame,text='Prototype: one item per sale/delivery; no login or receipt printer yet. Keep operational use on hold.',foreground='#975400').pack(anchor='w',pady=8)
refresh(); root.mainloop()
