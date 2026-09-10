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

require_once __DIR__ . '/web_bootstrap.php';

$status = cspoe_get_string('status', 12);
if (!in_array($status, ['active', 'gone', 'all'], true)) {
    $status = 'active';
}
$search = cspoe_get_string('q', 128);
$page = cspoe_page_number();
$pageSize = 25;

try {
    $client = CspoEClient::fromEnvironment();
    $total = $client->countLegacyDelegators($status, $search);
    $pages = max(1, (int) ceil($total / $pageSize));
    $page = min($page, $pages);
    $delegators = $client->legacyDelegators(
        $status,
        $search,
        $pageSize,
        ($page - 1) * $pageSize
    );
} catch (Throwable $error) {
    cspoe_render_error($error, 'delegators');
}

cspoe_page_start('Délégataires', 'delegators');
?>

<section class="panel">
    <div class="panel-header"><h2>Rechercher et filtrer</h2></div>
    <div class="panel-body">
        <form class="filters" method="get" action="delegators.php">
            <label>
                Adresse de stake
                <input type="search" name="q" value="<?= cspoe_h($search) ?>"
                       maxlength="128" placeholder="stake1…">
            </label>
            <label>
                Statut
                <select name="status">
                    <option value="active" <?= $status === 'active' ? 'selected' : '' ?>>Actifs</option>
                    <option value="gone" <?= $status === 'gone' ? 'selected' : '' ?>>Sortis</option>
                    <option value="all" <?= $status === 'all' ? 'selected' : '' ?>>Tous</option>
                </select>
            </label>
            <button type="submit">Appliquer</button>
        </form>
    </div>
</section>

<section class="panel">
    <div class="panel-header">
        <h2>Liste des délégataires</h2>
        <span><?= cspoe_integer($total) ?> résultat<?= $total > 1 ? 's' : '' ?></span>
    </div>
    <?php if ($delegators === []): ?>
        <div class="panel-body"><?php cspoe_empty('Aucun délégataire ne correspond aux filtres.'); ?></div>
    <?php else: ?>
        <div class="table-wrap">
            <table>
                <thead>
                <tr>
                    <th>Adresse</th>
                    <th>Statut</th>
                    <th class="numeric">Depuis</th>
                    <th class="numeric">Epochs</th>
                    <th class="numeric">Stake</th>
                    <th class="numeric">Récompenses</th>
                    <th class="numeric">Bonus</th>
                    <th class="numeric">Loyauté</th>
                </tr>
                </thead>
                <tbody>
                <?php foreach ($delegators as $row): ?>
                    <tr>
                        <td class="address">
                            <a href="<?= cspoe_h(cspoe_query_url('delegator.php', ['stake_address' => $row['stake_address']])) ?>"
                               title="<?= cspoe_h($row['stake_address']) ?>"><?= cspoe_h(cspoe_address($row['stake_address'])) ?></a>
                        </td>
                        <td>
                            <?php if ((int) $row['gone_epoch'] === 0): ?>
                                <span class="badge">Actif</span>
                            <?php else: ?>
                                <span class="badge gone">Sorti en <?= cspoe_integer($row['gone_epoch']) ?></span>
                            <?php endif; ?>
                        </td>
                        <td class="numeric"><?= cspoe_integer($row['since_epoch']) ?></td>
                        <td class="numeric"><?= cspoe_integer($row['epoch_count']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['stake']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['rewards_sum']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['bonus_sum']) ?></td>
                        <td class="numeric"><?= cspoe_percent($row['loyalty']) ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    <?php endif; ?>
</section>

<?php
cspoe_pagination(
    'delegators.php',
    $page,
    $pageSize,
    $total,
    ['status' => $status, 'q' => $search]
);
cspoe_page_end();
