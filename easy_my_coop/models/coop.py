# -*- coding: utf-8 -*-
from datetime import datetime

from openerp import api, fields, models, _
from openerp.addons.base_iban import base_iban
from openerp.exceptions import UserError, ValidationError

_REQUIRED = ['email',
             'firstname',
             'lastname',
             'birthdate',
             'address',
             'share_product_id',
             'ordered_parts',
             'zip_code',
             'city',
             'iban',
             'no_registre',
             'gender']  # Could be improved including required from model


@api.model
def _lang_get(self):
    languages = self.env['res.lang'].search([])
    return [(language.code, language.name) for language in languages]


class subscription_request(models.Model):
    _name = 'subscription.request'
    _description = 'Subscription Request'

    def get_required_field(self):
        return _REQUIRED

    @api.model
    def create(self, vals):
        partner_obj = self.env['res.partner']
        if not vals.get('partner_id'):
            cooperator = False
            if vals.get('no_registre'):
                cooperator = partner_obj.get_cooperator_from_nin(
                                            vals.get('no_registre'))
            if cooperator:
                # TODO remove the following line of code once it has
                # been founded a way to avoid dubble entry
                cooperator = cooperator[0]
                if cooperator.member:
                    vals['type'] = 'increase'
                    vals['already_cooperator'] = True
                else:
                    vals['type'] = 'subscription'
                vals['partner_id'] = cooperator.id

                if not cooperator.cooperator:
                    cooperator.write({'cooperator': True})
        else:
            cooperator_id = vals.get('partner_id')
            cooperator = partner_obj.browse(cooperator_id)
            if cooperator.member:
                    vals['type'] = 'increase'
                    vals['already_cooperator'] = True

        subscr_request = super(subscription_request, self).create(vals)

        confirmation_mail_template = self.env.ref('easy_my_coop.email_template_confirmation', False)
        confirmation_mail_template.send_mail(subscr_request.id)

        return subscr_request

    @api.model
    def create_comp_sub_req(self, vals):
        if not vals.get('partner_id'):
            cooperator = self.env['res.partner'].get_cooperator_from_crn(vals.get('company_register_number'))
            if cooperator:
                vals['partner_id'] = cooperator.id
                vals['type'] = 'increase'
                vals['already_cooperator'] = True
        subscr_request = super(subscription_request, self).create(vals)

        confirmation_mail_template = self.env.ref('easy_my_coop.email_template_confirmation_company', False)
        confirmation_mail_template.send_mail(subscr_request.id, True)

        return subscr_request

    def check_belgian_identification_id(self, nat_register_num):
        if not self.check_empty_string(nat_register_num):
            return False
        if len(nat_register_num) != 11:
            return False
        if not nat_register_num.isdigit():
            return False
        birthday_number = nat_register_num[0:9]
        controle = nat_register_num[9:11]
        check_controle = 97 - (int(birthday_number) % 97)
        if int(check_controle) != int(controle):
            check_controle = 97 - ((2000000000 + int(birthday_number)) % 97)
            if int(check_controle) != int(controle):
                return False
        return True

    def check_empty_string(self, value):
        if value is None or value is False or value == '':
            return False
        return True

    @api.multi
    @api.depends('iban', 'no_registre', 'skip_control_ng', 'is_company')
    def _validated_lines(self):
        for sub_request in self:
            validated = False
            try:
                base_iban.validate_iban(sub_request.iban)
                validated = True
            except ValidationError:
                validated = False

            # if not sub_request.is_company:
            if sub_request.skip_control_ng \
                    or self.check_belgian_identification_id(
                                        sub_request.no_registre):
                validated = True
            else:
                validated = False
            sub_request.validated = validated

    @api.multi
    @api.depends('share_product_id',
                 'share_product_id.list_price',
                 'ordered_parts')
    def _compute_subscription_amount(self):
        for sub_request in self:
            sub_request.subscription_amount = sub_request.share_product_id.list_price * sub_request.ordered_parts

    already_cooperator = fields.Boolean(string="I'm already cooperator")
    name = fields.Char(string='Name',
                       required=True)
    firstname = fields.Char(string='Firstname')
    lastname = fields.Char(string='Lastname')
    birthdate = fields.Date(string="Birthdate")
    gender = fields.Selection([('male', _('Male')),
                               ('female', _('Female')),
                               ('other', _('Other'))], string='Gender')
    type = fields.Selection([('new', 'New Cooperator'),
                             ('subscription', 'Subscription'),
                             ('increase', 'Increase number of share')],
                            string='Type', default="new")
    state = fields.Selection([('draft', 'Draft'),
                              ('block', 'Blocked'),
                              ('done', 'Done'),
                              ('waiting', 'Waiting'),
                              ('transfer', 'Transfer'),
                              ('cancelled', 'Cancelled'),
                              ('paid', 'paid')],
                             string='State', required=True, default="draft")
    email = fields.Char(string='Email', required=True)
    iban = fields.Char(string='Account Number')
    partner_id = fields.Many2one('res.partner',
                                 string='Cooperator')
    share_product_id = fields.Many2one('product.product',
                                       string='Share type',
                                       domain=[('is_share', '=', True)],
                                       required=True)
    share_short_name = fields.Char(related='share_product_id.short_name',
                                   string='Share type name')
    share_unit_price = fields.Float(related='share_product_id.list_price',
                                    string='Share price')
    subscription_amount = fields.Float(compute='_compute_subscription_amount',
                                       string='Subscription amount')
    ordered_parts = fields.Integer(string='Number of Share',
                                   required=True)
    address = fields.Char(string='Address',
                          required=True)
    city = fields.Char(string='City',
                       required=True)
    zip_code = fields.Char(string='Zip Code',
                           required=True)
    country_id = fields.Many2one('res.country',
                                 string='Country',
                                 ondelete='restrict',
                                 required=True)
    phone = fields.Char(string='Phone')
    no_registre = fields.Char(string='National Register Number')
    user_id = fields.Many2one('res.users',
                              string='Responsible',
                              readonly=True)
    validated = fields.Boolean(compute='_validated_lines',
                               string='Valid Line?',
                               readonly=True)
    skip_control_ng = fields.Boolean(string="Skip control",
                                     help="if this field is checked then no"
                                     " control will be done on the national"
                                     " register number and on the iban bank"
                                     " account. To be done in case of the id"
                                     " card is from abroad or in case of"
                                     " a passport")
    lang = fields.Selection(_lang_get,
                            string='Language',
                            required=True,
                            default=lambda self: self.env['res.company']._company_default_get().default_lang_id.code)
    date = fields.Date(string='Subscription date request',
                       required=True,
                       default=lambda self: datetime.strftime(datetime.now(), '%Y-%m-%d'))
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 change_default=True,
                                 readonly=True,
                                 default=lambda self: self.env['res.company']._company_default_get())
    is_company = fields.Boolean(string='Is a company')
    is_operation = fields.Boolean(string='Is an operation')
    company_name = fields.Char(string="Company name")
    company_email = fields.Char(string="Company email")
    company_register_number = fields.Char(string='Company register number')
    company_type = fields.Selection([('scrl', 'SCRL'),
                                     ('asbl', 'ASBL'),
                                     ('sprl', 'SPRL'),
                                     ('sa', 'SA'),
                                     ('other', 'Other')])
    same_address = fields.Boolean(string='Same address')
    activities_address = fields.Char(string='Activities address')
    activities_city = fields.Char(string='Activities city')
    activities_zip_code = fields.Char(string='Activities zip Code')
    activities_country_id = fields.Many2one('res.country',
                                            string='Activities country',
                                            ondelete='restrict')
    contact_person_function = fields.Char(string='Function')
    operation_request_id = fields.Many2one('operation.request',
                                           string="Operation Request")
    is_operation = fields.Boolean(string="Is Operation request")
    capital_release_request = fields.One2many('account.invoice',
                                              'subscription_request',
                                              string='Capital release request',
                                              readonly=True)
    capital_release_request_date = fields.Date(string="Force the capital release request date",
                                               help="Keep empty to use the current date",
                                               copy=False)
    source = fields.Selection([('website', 'Website'),
                               ('crm', 'CRM'),
                               ('manual', 'Manual'),
                               ('operation', 'Operation')],
                              string="Source",
                              default="website")
    _order = "id desc"

    # declare this function in order to be overriden
    def get_eater_vals(self, partner, share_product_id):
        return {}

    def _prepare_invoice_line(self, product, partner, qty):
        self.ensure_one()
        account = product.property_account_income_id \
            or product.categ_id.property_account_income_categ_id
        if not account:
            raise UserError(_('Please define income account for this product:'
                              ' "%s" (id:%d) - or for its category: "%s".') %
                            (product.name, product.id, product.categ_id.name))

        fpos = partner.property_account_position_id
        if fpos:
            account = fpos.map_account(account)

        res = {
            'name': product.name,
            'account_id': account.id,
            'price_unit': product.lst_price,
            'quantity': qty,
            'uom_id': product.uom_id.id,
            'product_id': product.id or False,
        }
        return res

    def send_capital_release_request(self, invoice):
        invoice_email_template = self.env['mail.template'].search([('name', '=', 'Request to Release Capital - Send by Email')])[0]

        # we send the email with the capital release request in attachment
        invoice_email_template.send_mail(invoice.id, True)
        invoice.sent = True

    def create_invoice(self, partner):
        # get subscription journal
        journal = self.env['account.journal'].search([('code', '=', 'SUBJ')])[0]
        # get the account for associate
        # TODO this should be defined in configuration
        if self.company_id.property_cooperator_account:
            account = self.company_id.property_cooperator_account
        else:
            account = self.env['account.account'].search([('code', '=', '416000')])[0]

        # creating invoice and invoice lines
        invoice_vals = {'partner_id': partner.id,
                        'journal_id': journal.id,
                        'account_id': account.id,
                        'type': 'out_invoice',
                        'release_capital_request': True,
                        'subscription_request': self.id}
        if self.capital_release_request_date:
            invoice_vals['date_invoice'] = self.capital_release_request_date
        invoice = self.env['account.invoice'].create(invoice_vals)
        vals = self._prepare_invoice_line(self.share_product_id, partner,
                                          self.ordered_parts)
        vals['invoice_id'] = invoice.id
        self.env['account.invoice.line'].create(vals)

        # validate the capital release request
        invoice.signal_workflow('invoice_open')

        self.send_capital_release_request(invoice)

        return invoice

    def get_partner_company_vals(self):
        partner_vals = {'name': self.company_name,
                        'is_company': self.is_company,
                        'company_register_number': self.company_register_number,
                        'customer': False, 'cooperator': True,
                        'street': self.address, 'zip': self.zip_code,
                        'city': self.city, 'email': self.company_email,
                        'out_inv_comm_type': 'bba',
                        'customer': self.share_product_id.customer,
                        'out_inv_comm_algorithm': 'random',
                        'country_id': self.country_id.id,
                        'lang': self.lang}
        return partner_vals

    def get_partner_vals(self):
        partner_vals = {'name': self.name, 'first_name': self.firstname,
                        'last_name': self.lastname, 'street': self.address,
                        'zip': self.zip_code, 'email': self.email,
                        'gender': self.gender, 'cooperator': True,
                        'city': self.city, 'phone': self.phone,
                        'national_register_number': self.no_registre,
                        'out_inv_comm_type': 'bba',
                        'out_inv_comm_algorithm': 'random',
                        'country_id': self.country_id.id, 'lang': self.lang,
                        'birthdate_date': self.birthdate,
                        'customer': self.share_product_id.customer}
        return partner_vals

    def create_coop_partner(self):
        partner_obj = self.env['res.partner']

        if self.is_company:
            partner_vals = self.get_partner_company_vals()
        else:
            partner_vals = self.get_partner_vals()

        partner = partner_obj.create(partner_vals)
        if self.iban:
            self.env['res.partner.bank'].create({
                    'partner_id': partner.id,
                    'acc_number': self.iban
                    })
        return partner

    def create_user(self, partner):
        user_obj = self.env['res.users']
        # TODO replace self by partner
        email = self.email
        if self.is_company:
            email = self.company_email

        user = user_obj.search([('login', '=', email)])
        if not user:
            user_values = {'partner_id': partner.id, 'login': email}
            user_id = user_obj.sudo()._signup_create_user(user_values)
            user = user_obj.browse(user_id)
            user.sudo().with_context({'create_user': True}).action_reset_password()

        return True

    @api.one
    def validate_subscription_request(self):
        partner_obj = self.env['res.partner']

        if self.ordered_parts <= 0:
            raise UserError(_('Number of share must be greater than 0.'))
        if self.partner_id:
            if not self.partner_id.cooperator:
                self.partner_id.cooperator = True
            partner = self.partner_id
        else:
            if self.already_cooperator:
                raise UserError(_('The checkbox already cooperator is'
                                  ' checked please select a cooperator.'))
            elif self.is_company and self.company_register_number:
                partner = partner_obj.search([('company_register_number', '=', self.company_register_number)])
            elif self.no_registre:
                partner = partner_obj.search([('national_register_number', '=', self.no_registre)])
            else:
                partner = None

        if not partner:
            partner = self.create_coop_partner()
        else:
            partner = partner[0]

        if self.is_company and not partner.has_representative():
            contact = False
            if self.no_registre:
                contact = partner_obj.search([('national_register_number', '=', self.no_registre)])
                if contact:
                    contact.type = 'representative'
            if not contact:
                contact_vals = {'name': self.name,
                                'first_name': self.firstname,
                                'last_name': self.lastname, 'customer': False,
                                'is_company': False, 'cooperator': True,
                                'street': self.address, 'gender': self.gender,
                                'zip': self.zip_code, 'city': self.city,
                                'phone': self.phone, 'email': self.email,
                                'national_register_number': self.no_registre,
                                'country_id': self.country_id.id,
                                'out_inv_comm_type': 'bba',
                                'out_inv_comm_algorithm': 'random',
                                'lang': self.lang,
                                'birthdate_date': self.birthdate,
                                'parent_id': partner.id,
                                'representative': True,
                                'function': self.contact_person_function,
                                'type': 'representative'}
                contact = partner_obj.create(contact_vals)
            else:
                if len(contact) > 1:
                    raise UserError(_('There is two different persons with the'
                                      ' same national register number. Please'
                                      ' proceed to a merge before to continue')
                                    )
                if contact.parent_id and contact.parent_id.id != partner.id:
                    raise UserError(_('This contact person is already defined'
                                      ' for another company. Please select'
                                      ' another contact'))
                else:
                    contact.write({'parent_id': partner.id,
                                   'representative': True})

        invoice = self.create_invoice(partner)
        self.write({'partner_id': partner.id, 'state': 'done'})

        self.create_user(partner)

        return invoice

    @api.one
    def block_subscription_request(self):
        self.write({'state': 'block'})

    @api.one
    def unblock_subscription_request(self):
        self.write({'state': 'draft'})

    @api.one
    def cancel_subscription_request(self):
        self.write({'state': 'cancelled'})

    @api.one
    def put_on_waiting_list(self):
        self.write({'state': 'waiting'})


class share_line(models.Model):
    _name = 'share.line'

    @api.multi
    def _compute_total_line(self):
        res = {}
        for line in self:
            line.total_amount_line = line.share_unit_price * line.share_number
        return res

    share_product_id = fields.Many2one('product.product',
                                       string='Share type',
                                       required=True,
                                       readonly=True)
    share_number = fields.Integer(string='Number of Share',
                                  required=True,
                                  readonly=True)
    share_short_name = fields.Char(related='share_product_id.short_name',
                                   string='Share type name')
    share_unit_price = fields.Float(string='Share price',
                                    readonly=True)
    effective_date = fields.Date(string='Effective Date',
                                 readonly=True)
    partner_id = fields.Many2one('res.partner',
                                 string='Cooperator',
                                 required=True,
                                 ondelete='cascade',
                                 readonly=True)
    total_amount_line = fields.Float(compute='_compute_total_line',
                                     string='Total amount line')


class subscription_register(models.Model):
    _name = 'subscription.register'

    @api.multi
    def _compute_total_line(self):
        for register_line in self:
            register_line.total_amount_line = register_line.share_unit_price * register_line.quantity

    name = fields.Char(string='Register Number Operation',
                       required=True,
                       readonly=True)
    register_number_operation = fields.Integer(string='Register Number Operation',
                                               required=True,
                                               readonly=True)
    partner_id = fields.Many2one('res.partner',
                                 string='Cooperator',
                                 required=True,
                                 readonly=True)
    partner_id_to = fields.Many2one('res.partner',
                                    string='Transfered to',
                                    readonly=True)
    date = fields.Date(string='Subscription Date',
                       required=True,
                       readonly=True)
    quantity = fields.Integer(string='Number of share',
                              readonly=True)
    share_unit_price = fields.Float(string='Share price',
                                    readonly=True)
    total_amount_line = fields.Float(compute='_compute_total_line',
                                     string='Total amount line')
    share_product_id = fields.Many2one('product.product',
                                       string='Share type',
                                       required=True,
                                       readonly=True,
                                       domain=[('is_share', '=', True)])
    share_short_name = fields.Char(related='share_product_id.short_name',
                                   string='Share type name',
                                   readonly=True)
    share_to_product_id = fields.Many2one('product.product',
                                          string='Share to type',
                                          readonly=True,
                                          domain=[('is_share', '=', True)])
    share_to_short_name = fields.Char(related='share_to_product_id.short_name',
                                      string='Share to type name',
                                      readonly=True)
    quantity_to = fields.Integer(string='Number of share to',
                                 readonly=True)
    share_to_unit_price = fields.Float(string='Share to price',
                                       readonly=True)
    type = fields.Selection([('subscription', 'Subscription'),
                             ('transfer', 'Transfer'),
                             ('sell_back', 'Sell Back'),
                             ('convert', 'Conversion')],
                            string='Operation Type', readonly=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True,
                                 change_default=True, readonly=True,
                                 default=lambda self: self.env['res.company']._company_default_get())
    user_id = fields.Many2one('res.users',
                              string='Responsible',
                              readonly=True,
                              default=lambda self: self.env.user)

    _order = "register_number_operation asc"

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None,
                   orderby=False,
                   lazy=True):
        if 'share_unit_price' in fields:
            fields.remove('share_unit_price')
        if 'register_number_operation' in fields:
            fields.remove('register_number_operation')
        res = super(subscription_register, self).read_group(domain, fields,
                                                            groupby,
                                                            offset=offset,
                                                            limit=limit,
                                                            orderby=orderby,
                                                            lazy=lazy)
        if 'total_amount_line' in fields:
            for line in res:
                if '__domain' in line:
                    lines = self.search(line['__domain'])
                    inv_value = 0.0
                    for line2 in lines:
                        inv_value += line2.total_amount_line
                    line['total_amount_line'] = inv_value
        return res
