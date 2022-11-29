# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import except_orm, UserError, ValidationError

class wizard_factura_global(models.TransientModel):
    _inherit = 'wizard.factura.global'

    max_amount = fields.Float (string='Monto Max') 

 
    def crear_factura(self):
        metodos_pago={}
        all_pedidos_pos =self.pedidos_pos
        if self.max_amount:
            pedidos_no_efectivo= self.env['pos.order']
            for pedido in self.pedidos_pos:
                if not all(payment.payment_method_id.is_cash_count for payment in pedido.payment_ids): 
                    pedidos_no_efectivo |=pedido
            total_no_efectivo = sum ([p.amount_total for p in pedidos_no_efectivo ])
            if total_no_efectivo > self.max_amount:
                raise ValidationError ('El Monto Max al menos debe ser de:  %.2f o cambie los pedidos elegidos.' %(total_no_efectivo))
            pedidos_incluidos= self.env['pos.order'] 
            pedidos_incluidos |= pedidos_no_efectivo
            amount=total_no_efectivo
            pedidos_no_incluidos = self.pedidos_pos -pedidos_incluidos
            pedidos_pos_ordenados= self.env['pos.order'].search([('id','in',pedidos_no_incluidos.ids)], order="amount_total asc")
            
            pedidos_no_incluidos_con_ieps= self.env['pos.order'] 
            

            for pedido in pedidos_pos_ordenados:
                if any('IEPS' in tax.name for tax in pedido.lines.tax_ids_after_fiscal_position):
                    pedidos_no_incluidos_con_ieps |= pedido
                    continue
                amount += pedido.amount_total
                if amount < self.max_amount:
                    pedidos_incluidos |=pedido
                else:
                    break
            if self.max_amount > amount and pedidos_no_incluidos_con_ieps:
                # Try to add pedidos_no_incluidos_con_ieps
                pedidos_pos_ordenados_con_ieps= self.env['pos.order'].search([('id','in',pedidos_no_incluidos_con_ieps.ids)], order="amount_total asc")
                for pedido in pedidos_pos_ordenados_con_ieps:
                    amount += pedido.amount_total
                    if amount < self.max_amount:
                        pedidos_incluidos |=pedido
                    else:
                        break

            self.pedidos_pos = pedidos_incluidos
        
        self._update_devoluciones_pos()
        for pedido in self.pedidos_pos+ self.devoluciones_pos:
            for payment in pedido.payment_ids:
                if not payment.payment_method_id.l10n_mx_edi_payment_method_id.id in metodos_pago.keys():
                    metodos_pago[payment.payment_method_id.l10n_mx_edi_payment_method_id.id]= payment.amount
                else:
                    metodos_pago[payment.payment_method_id.l10n_mx_edi_payment_method_id.id]+=payment.amount   
            for line in pedido.lines:
                product_taxes_ids = [tax for tax in line.product_id.taxes_id if tax.company_id.id == line.order_id.company_id.id ]
                cuenta=0
                for tax in product_taxes_ids:
                    if tax.f_global:
                        cuenta+=1
                if cuenta > 1 :
                    raise except_orm('Error','El pedido %s contiene el product : %s con mas de un impuesto para generar la factura global' %(pedido.name,line.product_id.name))

        if not self.pedidos_pos:
            raise ValidationError('No pudieron elegir pedidos para generar la factura global. Pruebe subiendo el número de pedidos o el monto.')

        invoice_obj=self.env['account.move']
        acc = self.invoice_partner.property_account_receivable_id.id
        inv = {
            'f_global': True,
            'invoice_origin': 'Ordenes del Pos',
            'journal_id': self.journal_pedidos.id or None,
            'move_type': 'out_invoice',
            'partner_id': self.invoice_partner.id,
            'narration': 'Factura del %s al %s' %(self.fecha_inicial, self.fecha_final),
            }
        #inv.update(invoice_obj.onchange_partner_id('out_invoice', self.invoice_partner.id)['value'])
        max_metodo_pago=max(metodos_pago, key=lambda k: metodos_pago[k])
        inv['l10n_mx_edi_payment_method_id']=max_metodo_pago or None
        inv['l10n_mx_edi_usage']='P01'
#Este loop genera un arreglo con las lineas por tipo de impuesto
        inv['invoice_line_ids']=[]
        detalle_impuestos={} 
        for pedido in self.pedidos_pos: 
            for line in pedido.lines:
                taxes=line.tax_ids_after_fiscal_position.ids
                tax_key='0'
                for tax in taxes:
                    if tax_key=='0': 
                        tax_key+=str(tax)
                    else:
                        tax_key+= ","+str(tax)
                if  tax_key in detalle_impuestos.keys():
                    detalle_impuestos[tax_key] += line.tax_ids_after_fiscal_position and line.tax_ids_after_fiscal_position[0].price_include and line.price_subtotal_incl or line.price_subtotal
                else:
                    detalle_impuestos[tax_key]  = line.tax_ids_after_fiscal_position and line.tax_ids_after_fiscal_position[0].price_include and line.price_subtotal_incl or line.price_subtotal


            '''
            Check if pedido has devoluciones
            '''
            devoluciones=self.devoluciones_pos.filtered(lambda order: order.pos_reference == pedido.pos_reference)
            if devoluciones:
                '''
                Actualizar detalle_impuestos
                '''
                for devolucion in devoluciones: 
                    for line in devolucion.lines:
                        taxes=line.tax_ids_after_fiscal_position.ids
                        tax_key='0'
                        for tax in taxes:
                            if tax_key=='0': 
                                tax_key+=str(tax)
                            else:
                                tax_key+= ","+str(tax)
                        if  tax_key in detalle_impuestos.keys():
                            detalle_impuestos[tax_key] += line.tax_ids_after_fiscal_position and line.tax_ids_after_fiscal_position[0].price_include and line.price_subtotal_incl or line.price_subtotal
                        else:
                            detalle_impuestos[tax_key]  = line.tax_ids_after_fiscal_position and line.tax_ids_after_fiscal_position[0].price_include and line.price_subtotal_incl or line.price_subtotal
        for key in detalle_impuestos.keys():
            tax_ids=key.split(",")
            tax_ids=[int(tax) for tax in tax_ids] 
            tax=self.env['account.tax'].browse(tax_ids)[0]
            if not tax or tax.amount==0.0:
                account_id=self.invoice_product.cuenta_tasa_0.id
            else:                    
                account_id=self.invoice_product.cuenta_tasa_16.id
            tax_ids =[key for key in tax_ids if key] 
            concepto= ','.join(self.env['account.tax'].browse([tax]).name for tax in tax_ids)
            inv["invoice_line_ids"].append((0,0,
                                   {
                                   'quantity': 1,
                                   'product_id':self.invoice_product.id,
                                   'product_uom_id':self.invoice_product.uom_id.id,
                                   'account_id':account_id,
                                   'name': 'Ingreso Gravado: %s' % (concepto),
                                   'discount': 0.0,
                                   'price_unit': detalle_impuestos[key],
                                   'tax_ids': [(6,0,tax_ids)],
                                   'analytic_account_id': self.analytic_account_id.id,
                                   })) 
        inv_id = invoice_obj.create(inv)
        if not inv_id:   
            raise except_orm('Error',' No se generó la factura')

        for pedido in self.pedidos_pos: 
            pedido.write({'account_move': inv_id.id,'state': 'invoiced'})
            '''
            Check if pedido has devoluciones
            '''
            devoluciones=self.devoluciones_pos.filtered(lambda order: order.pos_reference == pedido.pos_reference)
            if devoluciones:
                '''
                Actualizar 
                '''
                for devolucion in devoluciones: 
                    devolucion.write({'account_move': inv_id.id,'state': 'invoiced'})
         
        inv_id._onchange_partner_id()
        inv_id._compute_amount() # Esto calcula las lineas de impuesto correctamente
        # Disable pedidos pos
        left_pedidos_pos = all_pedidos_pos - self.pedidos_pos

        left_pedidos_pos.disabled = True
        
        mod_obj = self.env['ir.model.data']
        res = mod_obj.get_object_reference('account', 'view_move_form')
        res_id = res and res[1] or False
        return {
            'name': _('Customer Invoice'),
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': [res_id],
            'res_model': 'account.move',
            'context': "{'type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': inv_id.id,
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
