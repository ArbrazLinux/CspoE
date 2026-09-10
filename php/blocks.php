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
$page = cspoe_page_number();
$pageSize = 25;

try {
    $client = CspoEClient::fromEnvironment();
    $total = $client->countLegacyBlocks($epoch);
    $pages = max(1, (int) ceil($total / $pageSize));
    $page = min($page, $pages);
    $blocks = $client->legacyBlocks($epoch, $pageSize, ($page - 1) * $pageSize);
} catch (Throwable $error) {
    cspoe_render_error($error, 'blocks');
}

cspoe_page_start('Blocs produits', 'blocks');
?>

<section class="panel">
    <div class="panel-header"><h2>Filtrer par epoch</h2></div>
    <div class="panel-body">
        <form class="filters" method="get" action="blocks.php">
            <label>
                Numéro d’epoch
                <input type="number" name="epoch" min="0"
                       value="<?= $epoch === null ? '' : cspoe_h($epoch) ?>"
                       placeholder="Tous les epochs">
            </label>
            <button type="submit">Appliquer</button>
            <?php if ($epoch !== null): ?><a class="button" href="blocks.php">Effacer le filtre</a><?php endif; ?>
        </form>
    </div>
</section>

<section class="panel">
    <div class="panel-header">
        <h2><?= $epoch === null ? 'Historique complet' : 'Epoch ' . cspoe_integer($epoch) ?></h2>
        <span><?= cspoe_integer($total) ?> bloc<?= $total > 1 ? 's' : '' ?></span>
    </div>
    <?php if ($blocks === []): ?>
        <div class="panel-body"><?php cspoe_empty('Aucun bloc ne correspond à ce filtre.'); ?></div>
    <?php else: ?>
        <div class="table-wrap">
            <table>
                <thead>
                <tr>
                    <th>Epoch</th>
                    <th>Hash</th>
                    <th class="numeric">Hauteur</th>
                    <th class="numeric">Slot</th>
                    <th>Date UTC</th>
                    <th class="numeric">Transactions</th>
                    <th class="numeric">Frais</th>
                    <th class="numeric">Valeur</th>
                </tr>
                </thead>
                <tbody>
                <?php foreach ($blocks as $row): ?>
                    <tr>
                        <td><a href="<?= cspoe_h(cspoe_query_url('pool.php', ['epoch' => $row['epoch_epoch_number']])) ?>"><?= cspoe_integer($row['epoch_epoch_number']) ?></a></td>
                        <td class="address" title="<?= cspoe_h($row['hash']) ?>"><?= cspoe_h(cspoe_address($row['hash'], 12, 8)) ?></td>
                        <td class="numeric"><?= cspoe_integer($row['height']) ?></td>
                        <td class="numeric"><?= cspoe_integer($row['absolute_slot']) ?></td>
                        <td><?= cspoe_h($row['time']) ?></td>
                        <td class="numeric"><?= cspoe_integer($row['tx_count']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['fees']) ?></td>
                        <td class="numeric"><?= cspoe_ada($row['value']) ?></td>
                    </tr>
                <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    <?php endif; ?>
</section>

<?php
cspoe_pagination('blocks.php', $page, $pageSize, $total, ['epoch' => $epoch]);
cspoe_page_end();
