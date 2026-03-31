<?php
/**
 * Plugin Name: Veridata Zero Trust SSO
 * Description: Header-based SSO bypass for APISIX with JIT Provisioning.
 */

add_action('init', 'veridata_apisix_sso');

function veridata_apisix_sso() {
    // Se já tem sessão, não faz nada
    if (is_user_logged_in()) {
        return;
    }

    // Lê o Header injetado pelo APISIX
    if (isset($_SERVER['HTTP_X_USERINFO'])) {

        // O APISIX envia em Base64, decodificamos
        $json_payload = base64_decode($_SERVER['HTTP_X_USERINFO']);
        $user_data = json_decode($json_payload, true);

        if (isset($user_data['email'])) {
            $email = $user_data['email'];

            // Procura o usuário
            $user = get_user_by('email', $email);

            // JIT PROVISIONING: Se o usuário não existe, cria na hora
            if (!$user) {
                // Usa o e-mail como username e gera uma senha aleatória que nunca será usada
                $random_password = wp_generate_password(16, false);
                $user_id = wp_create_user($email, $random_password, $email);

                if (is_wp_error($user_id)) {
                    // Falha ao criar usuário, encerra a execução para não logar errado
                    error_log('Veridata SSO: Failed to create user ' . $email);
                    return;
                }

                $user = get_user_by('id', $user_id);

                // Opcional: Define a role padrão (ex: subscriber, editor, ou admin para testes)
                // $user->set_role('editor');
            }

            // Força o login do usuário (existente ou recém-criado)
            wp_clear_auth_cookie();
            wp_set_current_user($user->ID);
            wp_set_auth_cookie($user->ID);

            // Se bateu na tela de login, joga direto pro painel
            if (strpos($_SERVER['REQUEST_URI'], 'wp-login.php') !== false) {
                wp_redirect(admin_url());
                exit;
            }
        }
    }
}