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

$epoch = cspoe_get_positive_int('epoch');
$search = cspoe_get_string('q', 128);
$page = cspoe_page_number();
$pageSize = 25;

try {
    $client = CspoEClient::fromEnvironment();
    $total = $client->countLegacyBonuses($epoch, $search);
    $pages = max(1, (int) ceil($total / $pageSize));
    $page = min($page, $pages);
    $bonuses = $client->legacyBonuses(
        $epoch,
        $search,
        $pageSize,
        ($page - 1) * $pageSize
    );
} catch (Throwable $error) {
    cspoe_render_error($error, 'bonus');
}

cspoe_page_start('Bonus distribués', 'bonus');
?>

<section class="panel">
    <div class="panel-header"><h2>Rechercher et filtrer</h2></div>
    <div class="panel-body">
        <form class="filters" method="get" action="bonus.php">
            <label>
                Numéro d’epoch
                <input type="number" name="epoch" min="0"
                       value="<?= $epoch === null ? '' : cspoe_h($epoch) ?>"
                       placeholder="Tous les epochs">
            </label>
            <label>
                Adresse de stake
                <input type="search" name="q" maxlength="128"
                       value="<?= cspoe_h($search) ?>" placeholder="stake1…">
            </label>
            <button type="submit">Appliquer</button>
        </form>
    </div>
</section>

<section class="panel">
    <div class="panel-header">
        <h2>Attributions</h2>
        <span><?= cspoe_integer($total) ?> résultat<?= $total > 1 ? 's' : '' ?></span>
    </div>
    <?php if ($bonuses === []): ?>
        <div class="panel-body"><?php cspoe_empty('Aucun bonus ne correspond aux filtres.'); ?></div>
    <?php else: ?>
        <div class="table-wrap">
            <table>
                <thead>
                <tr>
                    <th>Epoch</th>
                    <th>Délégataire</th>
                    <th class="numeric">Montant</th>
                    <th class="numeric">Cumul à cet epoch</th>
                </tr>
                </thead>
                <tbody>
                <?php foreach ($bonuses as $row): ?>
                    <tr>
                        <td><a href="<?= cspoe_h(cspoe_query_url('pool.php', ['epoch' => $row['epoch_epoch_number']])) ?>"><?= cspoe_integer($row['epoch_epoch_number']) ?></a></td>
                        <td class="address">
                            <a href="<?= cspoe_h(cspoe_query_url('delegator.php', ['stake_address' => $row['delegator_stake_address']])) ?>"
                               title="<?= cspoe_h($row['delegator_stake_address']) ?>"><?= cspoe_h(cspoe_address($row['delegator_stake_address'])) ?></a>
                        </td>
                        <td class="numeric"><?= cspoe_ada($row['amount']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['sum']) ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    <?php endif; ?>
</section>

<?php
cspoe_pagination(
    'bonus.php',
    $page,
    $pageSize,
    $total,
    ['epoch' => $epoch, 'q' => $search]
);
cspoe_page_end();
