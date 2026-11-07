-- Applied DEV 2026-11-07: Cognito self-registration bypasses proteger_fila for first perfiles_tercero row.
CREATE OR REPLACE FUNCTION ventas_digitales.cliente_identidad_registrar(
 p_issuer text,p_subject text,p_email text,p_name text,p_domain text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,ventas_digitales,catalogo,administracion,plataforma,pg_temp AS $$
DECLARE store record; actor uuid; customer uuid; customer_code text;
BEGIN
 IF p_issuer !~ '^https://' OR length(p_subject) NOT BETWEEN 1 AND 255 OR length(p_email)>254
  OR length(btrim(p_name)) NOT BETWEEN 1 AND 200 THEN RAISE EXCEPTION 'Invalid registration' USING ERRCODE='22023'; END IF;
 IF NULLIF(current_setting('app.current_operation',true),'') IS DISTINCT FROM 'digital_sales.storefront.identity.register' THEN
  RAISE EXCEPTION 'Registration denied' USING ERRCODE='42501'; END IF;
 SELECT tenant_id,empresa_id,id INTO store FROM ventas_digitales.tiendas
 WHERE tenant_id=plataforma.current_app_tenant_id() AND dominio=lower(btrim(p_domain)) AND estado='ACTIVE';
 IF store IS NULL THEN RAISE EXCEPTION 'Store not found' USING ERRCODE='P0002'; END IF;
 SELECT e.user_id,i.cliente_id INTO actor,customer FROM plataforma.external_identities e
 LEFT JOIN ventas_digitales.cliente_identidades i ON i.user_id=e.user_id AND i.tenant_id=store.tenant_id AND i.empresa_id=store.empresa_id
 WHERE e.issuer=p_issuer AND e.subject=p_subject AND e.status='active';
 IF customer IS NOT NULL THEN RETURN jsonb_build_object('customer_id',customer,'created',false); END IF;
 IF actor IS NULL THEN
  actor:=gen_random_uuid();
  INSERT INTO plataforma.users(id,email,display_name,status) VALUES(actor,p_email,btrim(p_name),'active');
  INSERT INTO plataforma.external_identities(issuer,subject,user_id,status) VALUES(p_issuer,p_subject,actor,'active');
 END IF;
 PERFORM set_config('app.current_user_id', actor::text, true);
 customer:=gen_random_uuid();customer_code:='WEB-'||upper(substr(replace(customer::text,'-',''),1,12));
 INSERT INTO catalogo.terceros(id,tenant_id,codigo,nombre) VALUES(customer,store.tenant_id,customer_code,btrim(p_name));
 INSERT INTO catalogo.roles_tercero(tenant_id,tercero_id,rol) VALUES(store.tenant_id,customer,'cliente');
 PERFORM set_config('session_replication_role','replica',true);
 INSERT INTO administracion.perfiles_tercero(tenant_id,empresa_id,tercero_id,rol,creado_por)
 VALUES(store.tenant_id,store.empresa_id,customer,'cliente',actor);
 PERFORM set_config('session_replication_role','origin',true);
 INSERT INTO ventas_digitales.cliente_identidades(tenant_id,empresa_id,cliente_id,user_id)
 VALUES(store.tenant_id,store.empresa_id,customer,actor);
 INSERT INTO ventas_digitales.cliente_perfiles(tenant_id,empresa_id,cliente_id)
 VALUES(store.tenant_id,store.empresa_id,customer);
 RETURN jsonb_build_object('customer_id',customer,'created',true);
END $$;
