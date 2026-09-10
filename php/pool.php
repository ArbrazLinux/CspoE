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

$page = cspoe_page_number();
$pageSize = 20;
$requestedEpoch = cspoe_get_positive_int('epoch');

try {
    $client = CspoEClient::fromEnvironment();
    $latest = $client->legacyLatestEpoch();
    $selected = $requestedEpoch === null
        ? $latest
        : $client->legacyEpoch($requestedEpoch);
    $total = $client->countLegacyEpochs();
    $pages = max(1, (int) ceil($total / $pageSize));
    $page = min($page, $pages);
    $history = $client->legacyPoolHistory($pageSize, ($page - 1) * $pageSize);
} catch (Throwable $error) {
    cspoe_render_error($error, 'pool');
}

cspoe_page_start('État du pool', 'pool');

if ($selected === null) {
    cspoe_empty('Aucun epoch n’est encore disponible dans MySQL.');
    cspoe_page_end();
    exit;
}
?>

<section class="panel">
    <div class="panel-header">
        <h2>Epoch <?= cspoe_integer($selected['epoch_number']) ?></h2>
        <?php if ($latest !== null && $selected['epoch_number'] !== $latest['epoch_number']): ?>
            <a href="pool.php">Revenir au dernier epoch</a>
        <?php else: ?>
            <span class="badge">Dernières données</span>
        <?php endif; ?>
    </div>
    <div class="panel-body">
        <div class="grid cards">
            <article class="card"><small>Stake du pool</small><strong><?= cspoe_ada($selected['pool_stake']) ?></strong></article>
            <article class="card"><small>Délégataires</small><strong><?= cspoe_integer($selected['delegators_nb']) ?></strong></article>
            <article class="card"><small>Blocs de l’epoch</small><strong><?= cspoe_integer($selected['blocks']) ?></strong></article>
            <article class="card"><small>Blocs cumulés</small><strong><?= cspoe_integer($selected['blocks_sum']) ?></strong></article>
            <article class="card"><small>Récompenses du pool</small><strong><?= cspoe_ada($selected['pool_rewards']) ?></strong></article>
            <article class="card"><small>ROA du pool</small><strong><?= cspoe_percent($selected['pool_ROA_current']) ?></strong></article>
        </div>
        <dl class="definition-grid">
            <div><dt>Stake précédent</dt><dd><?= cspoe_ada($selected['pool_stake_previous']) ?></dd></div>
            <div><dt>Variation du stake</dt><dd><?= cspoe_ada($selected['pool_stake_diff']) ?></dd></div>
            <div><dt>Pledge</dt><dd><?= cspoe_ada($selected['pledge']) ?></dd></div>
            <div><dt>Propriétaires</dt><dd><?= cspoe_integer($selected['owners_nb']) ?></dd></div>
            <div><dt>Récompenses délégataires</dt><dd><?= cspoe_ada($selected['delegators_rewards']) ?></dd></div>
            <div><dt>Bonus distribués</dt><dd><?= cspoe_ada($selected['bonuses']) ?></dd></div>
        </dl>
    </div>
</section>

<section class="panel">
    <div class="panel-header">
        <h2>Historique des epochs</h2>
        <span><?= cspoe_integer($total) ?> epochs</span>
    </div>
    <div class="table-wrap">
        <table>
            <thead>
            <tr>
                <th>Epoch</th>
                <th class="numeric">Stake</th>
                <th class="numeric">Délégataires</th>
                <th class="numeric">Blocs</th>
                <th class="numeric">Récompenses</th>
                <th class="numeric">ROA</th>
            </tr>
            </thead>
            <tbody>
            <?php foreach ($history as $row): ?>
                <tr>
                    <td><a href="<?= cspoe_h(cspoe_query_url('pool.php', ['epoch' => $row['epoch_number']])) ?>"><?= cspoe_integer($row['epoch_number']) ?></a></td>
                    <td class="numeric"><?= cspoe_ada($row['pool_stake']) ?></td>
                    <td class="numeric"><?= cspoe_integer($row['delegators_nb']) ?></td>
                    <td class="numeric"><?= cspoe_integer($row['blocks']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['pool_rewards']) ?></td>
                    <td class="numeric"><?= cspoe_percent($row['pool_ROA_current']) ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>

<?php
cspoe_pagination('pool.php', $page, $pageSize, $total);
cspoe_page_end();
