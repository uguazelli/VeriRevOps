<?php
/**
 * Plugin Name: Veridata Zero Trust SSO
 * Description: Header-based SSO bypass for APISIX.
 */

add_action('init', 'veridata_apisix_sso');

function veridata_apisix_sso() {
    // Se já tem sessão, não faz nada
    if (is_user_logged_in()) {
        return;
    }

    // Lê o Header injetado pelo APISIX
    if (isset($_SERVER['HTTP_X_USERINFO'])) {

        // O APISIX envia em Base64, precisamos decodificar
        $json_payload = base64_decode($_SERVER['HTTP_X_USERINFO']);
        $user_data = json_decode($json_payload, true);

        // Extrai o e-mail validado
        if (isset($user_data['email'])) {
            $email = $user_data['email'];
            $user = get_user_by('email', $email);

            if ($user) {
                // Força o login sem senha!
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
}