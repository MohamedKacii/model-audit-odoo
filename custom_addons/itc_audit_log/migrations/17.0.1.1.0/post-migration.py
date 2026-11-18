def migrate(cr, version):
    # the state column is new and starts at "Brouillon" for every row, but these configurations were already auditing
    cr.execute("UPDATE audit_model_config SET state = 'running'")
