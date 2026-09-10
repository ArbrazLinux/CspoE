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

$stakeAddress = strtolower(cspoe_get_string('stake_address', 128));
$validAddress = $stakeAddress !== ''
    && preg_match('/^stake(?:_test)?1[0-9a-z]{20,120}$/', $stakeAddress) === 1;

if ($stakeAddress === '') {
    cspoe_page_start('Fiche délégataire', 'delegators');
    ?>
    <section class="panel">
        <div class="panel-header"><h2>Rechercher une adresse</h2></div>
        <div class="panel-body">
            <form class="filters" method="get" action="delegator.php">
                <label>
                    Adresse de stake complète
                    <input type="search" name="stake_address" maxlength="128"
                           required placeholder="stake1…">
                </label>
                <button type="submit">Afficher la fiche</button>
            </form>
        </div>
    </section>
    <?php
    cspoe_page_end();
    exit;
}

if (!$validAddress) {
    http_response_code(400);
    cspoe_page_start('Adresse invalide', 'delegators');
    cspoe_empty('L’adresse de stake fournie n’est pas valide.');
    cspoe_page_end();
    exit;
}

try {
    $client = CspoEClient::fromEnvironment();
    $delegator = $client->legacyDelegator($stakeAddress);
    $history = $delegator === null
        ? []
        : $client->legacyDelegatorHistory($stakeAddress);
    $departures = $delegator === null
        ? []
        : $client->legacyDelegatorDepartures($stakeAddress);
} catch (Throwable $error) {
    cspoe_render_error($error, 'delegators');
}

if ($delegator === null) {
    http_response_code(404);
    cspoe_page_start('Délégataire introuvable', 'delegators');
    cspoe_empty('Cette adresse n’existe pas dans l’historique CspoE.');
    cspoe_page_end();
    exit;
}

cspoe_page_start('Fiche délégataire', 'delegators');
?>

<section class="panel">
    <div class="panel-header">
        <h2 class="address wrap"><?= cspoe_h($stakeAddress) ?></h2>
        <?php if ((int) $delegator['gone_epoch'] === 0): ?>
            <span class="badge">Actif</span>
        <?php else: ?>
            <span class="badge gone">Sorti en <?= cspoe_integer($delegator['gone_epoch']) ?></span>
        <?php endif; ?>
    </div>
    <div class="panel-body">
        <div class="grid cards">
            <article class="card"><small>Stake actuel</small><strong><?= cspoe_ada($delegator['stake']) ?></strong></article>
            <article class="card"><small>Stake maximal</small><strong><?= cspoe_ada($delegator['stake_max']) ?></strong></article>
            <article class="card"><small>Récompenses cumulées</small><strong><?= cspoe_ada($delegator['rewards_sum']) ?></strong></article>
            <article class="card"><small>Bonus cumulés</small><strong><?= cspoe_ada($delegator['bonus_sum']) ?></strong></article>
            <article class="card"><small>Loyauté</small><strong><?= cspoe_percent($delegator['loyalty']) ?></strong></article>
            <article class="card"><small>ROA bonus inclus</small><strong><?= cspoe_percent($delegator['ROA_bonus_included']) ?></strong></article>
        </div>
        <dl class="definition-grid">
            <div><dt>Premier epoch</dt><dd><?= cspoe_integer($delegator['first_epoch']) ?></dd></div>
            <div><dt>Présent depuis</dt><dd><?= cspoe_integer($delegator['since_epoch']) ?></dd></div>
            <div><dt>Nombre d’epochs</dt><dd><?= cspoe_integer($delegator['epoch_count']) ?></dd></div>
            <div><dt>Retours</dt><dd><?= cspoe_integer($delegator['comeback_count']) ?></dd></div>
            <div><dt>Entrées cumulées</dt><dd><?= cspoe_ada($delegator['inputs_sum']) ?></dd></div>
            <div><dt>Sorties cumulées</dt><dd><?= cspoe_ada($delegator['outputs_sum']) ?></dd></div>
        </dl>
    </div>
</section>

<?php if ($departures !== []): ?>
<section class="panel">
    <div class="panel-header"><h2>Départs et retours</h2></div>
    <div class="table-wrap">
        <table>
            <thead><tr><th>Dernier epoch actif</th><th class="numeric">Stake perdu</th><th class="numeric">Perte cumulée</th><th class="numeric">Retour n°</th></tr></thead>
            <tbody>
            <?php foreach ($departures as $row): ?>
                <tr>
                    <td><?= cspoe_integer($row['epoch_epoch_number']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['lost_stake']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['lost_stake_sum']) ?></td>
                    <td class="numeric"><?= cspoe_integer($row['back_count']) ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>
<?php endif; ?>

<section class="panel">
    <div class="panel-header">
        <h2>Historique par epoch</h2>
        <span><?= cspoe_integer(count($history)) ?> lignes</span>
    </div>
    <div class="table-wrap">
        <table>
            <thead>
            <tr>
                <th>Epoch</th>
                <th class="numeric">Stake</th>
                <th class="numeric">Variation</th>
                <th class="numeric">Récompense</th>
                <th class="numeric">Bonus</th>
                <th class="numeric">ROA</th>
                <th class="numeric">ROA + bonus</th>
            </tr>
            </thead>
            <tbody>
            <?php foreach ($history as $row): ?>
                <tr>
                    <td><?= cspoe_integer($row['epoch_epoch_number']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['amount']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['diff']) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['reward_amount'] ?? 0) ?></td>
                    <td class="numeric"><?= cspoe_ada($row['bonus_amount'] ?? 0) ?></td>
                    <td class="numeric"><?= cspoe_percent($row['ROA_current']) ?></td>
                    <td class="numeric"><?= cspoe_percent($row['ROA_bonusincluded']) ?></td>
                </tr>
            <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</section>

<?php cspoe_page_end();
