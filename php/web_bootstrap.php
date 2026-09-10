<?php
/*
 * CspoE is developped and maintained by BreizhStakePool.io 
 *
 * Help us to improve this tool / Please consider a donation and/or delegation to [BZH].
 * Pool ID : 9b9ad921921db31ca91cd6dfdf11f5efee8c1ab94671a6b4a8edc748
 * donation address : addr1qyv0cv6ju9j25lx7daedsy5n0gtp0h0pf4e0rn0qzz3hesq8e4wmcqungnssk5hwp52hr0zazkx574n4s49gqzz7fqgq5j8nu2
 *
 * Consider delegate your voting power to our Breizh DRep [BZH] 
 * drep ID : drep1yf64m233qq6nutjpkh4uc7jncr2gxwtlsq7n68v38ka2l9qez8h3h
 */
declare(strict_types=1);

require_once __DIR__ . '/CspoEClient.php';

header('Content-Type: text/html; charset=utf-8');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: same-origin');
header("Content-Security-Policy: default-src 'self'; style-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");

function cspoe_h(mixed $value): string
{
    return htmlspecialchars((string) $value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function cspoe_get_string(string $name, int $maxLength = 160): string
{
    $value = filter_input(INPUT_GET, $name, FILTER_UNSAFE_RAW);
    if (!is_string($value)) {
        return '';
    }
    $value = trim($value);
    return substr($value, 0, $maxLength);
}

function cspoe_get_positive_int(string $name): ?int
{
    $value = filter_input(INPUT_GET, $name, FILTER_VALIDATE_INT, [
        'options' => ['min_range' => 0],
    ]);
    return $value === false || $value === null ? null : (int) $value;
}

function cspoe_page_number(): int
{
    $page = filter_input(INPUT_GET, 'page', FILTER_VALIDATE_INT, [
        'options' => ['min_range' => 1],
    ]);
    return $page === false || $page === null ? 1 : min((int) $page, 100000);
}

function cspoe_ada(mixed $lovelace): string
{
    $value = (int) $lovelace;
    $negative = $value < 0;
    $absolute = abs($value);
    $whole = intdiv($absolute, 1000000);
    $fraction = $absolute % 1000000;
    return ($negative ? '−' : '')
        . number_format($whole, 0, ',', ' ')
        . ',' . str_pad((string) $fraction, 6, '0', STR_PAD_LEFT)
        . ' ₳';
}

function cspoe_integer(mixed $value): string
{
    return number_format((int) $value, 0, ',', ' ');
}

function cspoe_percent(mixed $value): string
{
    return number_format((float) $value, 2, ',', ' ') . ' %';
}

function cspoe_address(string $address, int $head = 16, int $tail = 10): string
{
    if (strlen($address) <= $head + $tail + 1) {
        return $address;
    }
    return substr($address, 0, $head)
        . '…'
        . substr($address, -$tail);
}

function cspoe_query_url(string $page, array $parameters): string
{
    $filtered = array_filter(
        $parameters,
        static fn (mixed $value): bool => $value !== null && $value !== ''
    );
    $query = http_build_query($filtered, '', '&', PHP_QUERY_RFC3986);
    return $page . ($query === '' ? '' : '?' . $query);
}

function cspoe_page_start(string $title, string $active): void
{
    $items = [
        'pool' => ['pool.php', 'Pool'],
        'delegators' => ['delegators.php', 'Délégataires'],
        'blocks' => ['blocks.php', 'Blocs'],
        'bonus' => ['bonus.php', 'Bonus'],
    ];
    ?>
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="dark light">
    <title><?= cspoe_h($title) ?> — CspoE</title>
    <link rel="stylesheet" href="cspoe.css">
</head>
<body>
<header class="site-header">
    <div class="shell header-inner">
        <a class="brand" href="pool.php" aria-label="Accueil CspoE">
            <span class="brand-mark">C</span>
            <span><strong>CspoE</strong><small>Pool data</small></span>
        </a>
        <nav aria-label="Navigation principale">
            <?php foreach ($items as $key => [$href, $label]): ?>
                <a href="<?= cspoe_h($href) ?>"
                   <?= $key === $active ? 'aria-current="page"' : '' ?>><?= cspoe_h($label) ?></a>
            <?php endforeach; ?>
        </nav>
    </div>
</header>
<main class="shell">
    <div class="page-heading">
        <p class="eyebrow">Cardano SPO Engine</p>
        <h1><?= cspoe_h($title) ?></h1>
    </div>
    <?php
}

function cspoe_page_end(): void
{
    ?>
</main>
<footer class="site-footer">
    <div class="shell">Données générées par CspoE · Consultation en lecture seule</div>
</footer>
</body>
</html>
    <?php
}

function cspoe_render_error(Throwable $error, string $active): never
{
    error_log('CspoE PHP: ' . $error->getMessage());
    http_response_code(500);
    cspoe_page_start('Données indisponibles', $active);
    ?>
    <section class="notice error">
        <h2>Connexion aux données impossible</h2>
        <p>La projection MySQL de CspoE n’est pas disponible pour le moment.</p>
        <?php if (getenv('CSPOE_PHP_DEBUG') === '1'): ?>
            <pre><?= cspoe_h($error->getMessage()) ?></pre>
        <?php endif; ?>
    </section>
    <?php
    cspoe_page_end();
    exit;
}

function cspoe_empty(string $message): void
{
    ?>
    <div class="notice"><p><?= cspoe_h($message) ?></p></div>
    <?php
}

function cspoe_pagination(
    string $script,
    int $page,
    int $pageSize,
    int $total,
    array $parameters = []
): void {
    $pages = max(1, (int) ceil($total / $pageSize));
    if ($pages <= 1) {
        return;
    }
    ?>
    <nav class="pagination" aria-label="Pagination">
        <?php if ($page > 1): ?>
            <a href="<?= cspoe_h(cspoe_query_url($script, array_merge($parameters, ['page' => $page - 1]))) ?>">← Précédent</a>
        <?php else: ?>
            <span aria-disabled="true">← Précédent</span>
        <?php endif; ?>
        <strong>Page <?= cspoe_integer($page) ?> sur <?= cspoe_integer($pages) ?></strong>
        <?php if ($page < $pages): ?>
            <a href="<?= cspoe_h(cspoe_query_url($script, array_merge($parameters, ['page' => $page + 1]))) ?>">Suivant →</a>
        <?php else: ?>
            <span aria-disabled="true">Suivant →</span>
        <?php endif; ?>
    </nav>
    <?php
}
