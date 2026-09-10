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

/**
 * Client PDO en lecture seule pour les projections MySQL de CspoE.
 *
 * Les méthodes historiques publiques sont conservées afin de ne pas casser
 * les premiers appels PHP déjà intégrés au moteur.
 */
final class CspoEClient
{
    public function __construct(private PDO $pdo)
    {
        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $this->pdo->setAttribute(PDO::ATTR_EMULATE_PREPARES, false);
    }

    public static function fromEnvironment(): self
    {
        $fileConfig = [];
        $configPath = getenv('CSPOE_PHP_CONFIG') ?: '/etc/cspoe/php-db.php';
        if (is_file($configPath)) {
            $loaded = require $configPath;
            if (is_array($loaded)) {
                $fileConfig = $loaded;
            }
        }
        $value = static function (string $name, string $default = '') use ($fileConfig): string {
            $environment = getenv($name);
            if (is_string($environment) && $environment !== '') {
                return $environment;
            }
            return isset($fileConfig[$name]) ? (string) $fileConfig[$name] : $default;
        };
        $host = $value('MYSQL_HOST', '127.0.0.1');
        $port = $value('MYSQL_PORT', '3306');
        $database = $value('MYSQL_DATABASE');
        $user = $value('MYSQL_USER');
        $password = $value('MYSQL_PASSWORD');

        if ($database === '' || $user === '') {
            throw new RuntimeException(
                'MYSQL_DATABASE et MYSQL_USER doivent être configurés pour PHP'
            );
        }
        if (!ctype_digit((string) $port)) {
            throw new RuntimeException('MYSQL_PORT invalide');
        }

        $dsn = sprintf(
            'mysql:host=%s;port=%s;dbname=%s;charset=utf8mb4',
            $host,
            $port,
            $database
        );

        return new self(new PDO($dsn, $user, $password, [
            PDO::ATTR_TIMEOUT => 10,
        ]));
    }

    public function latestEpoch(): ?array
    {
        $query = $this->pdo->query(
            'SELECT * FROM cspoe_epochs ORDER BY epoch DESC LIMIT 1'
        );
        $row = $query->fetch();
        return $row === false ? null : $row;
    }

    public function epoch(int $epoch): ?array
    {
        $query = $this->pdo->prepare(
            'SELECT * FROM cspoe_epochs WHERE epoch = :epoch'
        );
        $query->execute(['epoch' => $epoch]);
        $row = $query->fetch();
        return $row === false ? null : $row;
    }

    public function snapshot(?int $epoch = null): ?array
    {
        if ($epoch === null) {
            $query = $this->pdo->query(
                'SELECT payload FROM cspoe_snapshots ORDER BY epoch DESC LIMIT 1'
            );
        } else {
            $query = $this->pdo->prepare(
                'SELECT payload FROM cspoe_snapshots WHERE epoch = :epoch'
            );
            $query->execute(['epoch' => $epoch]);
        }
        $row = $query->fetch();
        if ($row === false) {
            return null;
        }
        return json_decode($row['payload'], true, 512, JSON_THROW_ON_ERROR);
    }

    public function accounts(int $epoch, ?string $role = null): array
    {
        if ($role === null) {
            $query = $this->pdo->prepare(
                'SELECT * FROM cspoe_accounts WHERE epoch = :epoch '
                . 'ORDER BY account_role, list_position'
            );
            $query->execute(['epoch' => $epoch]);
        } else {
            $query = $this->pdo->prepare(
                'SELECT * FROM cspoe_accounts WHERE epoch = :epoch '
                . 'AND account_role = :role ORDER BY list_position'
            );
            $query->execute(['epoch' => $epoch, 'role' => $role]);
        }
        return $query->fetchAll();
    }

    /** Contrat SQL exact utilisé par le site historique. */
    public function legacyLatestEpoch(): ?array
    {
        $query = $this->pdo->query(
            'SELECT * FROM `epoch` ORDER BY epoch_number DESC LIMIT 1'
        );
        $row = $query->fetch();
        return $row === false ? null : $row;
    }

    public function legacyEpoch(int $epoch): ?array
    {
        $query = $this->pdo->prepare(
            'SELECT * FROM `epoch` WHERE epoch_number = :epoch'
        );
        $query->execute(['epoch' => $epoch]);
        $row = $query->fetch();
        return $row === false ? null : $row;
    }

    public function legacyPoolHistory(int $limit, int $offset): array
    {
        $query = $this->pdo->prepare(
            'SELECT * FROM `epoch` ORDER BY epoch_number DESC LIMIT :limit OFFSET :offset'
        );
        $query->bindValue(':limit', $limit, PDO::PARAM_INT);
        $query->bindValue(':offset', $offset, PDO::PARAM_INT);
        $query->execute();
        return $query->fetchAll();
    }

    public function countLegacyEpochs(): int
    {
        return (int) $this->pdo->query('SELECT COUNT(*) FROM `epoch`')->fetchColumn();
    }

    public function legacyDelegator(string $stakeAddress): ?array
    {
        $query = $this->pdo->prepare(
            'SELECT * FROM delegator WHERE stake_address = :stake_address'
        );
        $query->execute(['stake_address' => $stakeAddress]);
        $row = $query->fetch();
        return $row === false ? null : $row;
    }

    public function legacyDelegators(
        string $status,
        string $search,
        int $limit,
        int $offset
    ): array {
        [$where, $parameters] = $this->delegatorFilters($status, $search);
        $query = $this->pdo->prepare(
            'SELECT * FROM delegator ' . $where
            . ' ORDER BY stake DESC, stake_address ASC LIMIT :limit OFFSET :offset'
        );
        foreach ($parameters as $name => $value) {
            $query->bindValue($name, $value, PDO::PARAM_STR);
        }
        $query->bindValue(':limit', $limit, PDO::PARAM_INT);
        $query->bindValue(':offset', $offset, PDO::PARAM_INT);
        $query->execute();
        return $query->fetchAll();
    }

    public function countLegacyDelegators(string $status, string $search): int
    {
        [$where, $parameters] = $this->delegatorFilters($status, $search);
        $query = $this->pdo->prepare('SELECT COUNT(*) FROM delegator ' . $where);
        $query->execute($parameters);
        return (int) $query->fetchColumn();
    }

    private function delegatorFilters(string $status, string $search): array
    {
        $clauses = [];
        $parameters = [];

        if ($status === 'active') {
            $clauses[] = 'gone_epoch = 0';
        } elseif ($status === 'gone') {
            $clauses[] = 'gone_epoch > 0';
        }

        if ($search !== '') {
            $clauses[] = 'stake_address LIKE :search';
            $parameters[':search'] = '%' . $search . '%';
        }

        return [
            $clauses === [] ? '' : 'WHERE ' . implode(' AND ', $clauses),
            $parameters,
        ];
    }

    public function legacyDelegatorHistory(string $stakeAddress): array
    {
        $query = $this->pdo->prepare(
            'SELECT s.*, r.amount AS reward_amount, r.sum AS reward_sum, '
            . 'b.amount AS bonus_amount, b.sum AS bonus_sum '
            . 'FROM stake s '
            . 'LEFT JOIN rewards r ON r.epoch_epoch_number = s.epoch_epoch_number '
            . 'AND r.delegator_stake_address = s.delegator_stake_address '
            . 'LEFT JOIN bonus b ON b.epoch_epoch_number = s.epoch_epoch_number '
            . 'AND b.delegator_stake_address = s.delegator_stake_address '
            . 'WHERE s.delegator_stake_address = :stake_address '
            . 'ORDER BY s.epoch_epoch_number DESC'
        );
        $query->execute(['stake_address' => $stakeAddress]);
        return $query->fetchAll();
    }

    public function legacyDelegatorDepartures(string $stakeAddress): array
    {
        $query = $this->pdo->prepare(
            'SELECT * FROM gone_delegators '
            . 'WHERE delegator_stake_address = :stake_address '
            . 'ORDER BY epoch_epoch_number DESC, back_count DESC'
        );
        $query->execute(['stake_address' => $stakeAddress]);
        return $query->fetchAll();
    }

    public function legacyBlocks(?int $epoch, int $limit, int $offset): array
    {
        $where = $epoch === null ? '' : 'WHERE b.epoch_epoch_number = :epoch ';
        $query = $this->pdo->prepare(
            'SELECT b.* FROM blocks b ' . $where
            . 'ORDER BY b.epoch_epoch_number DESC, b.height DESC '
            . 'LIMIT :limit OFFSET :offset'
        );
        if ($epoch !== null) {
            $query->bindValue(':epoch', $epoch, PDO::PARAM_INT);
        }
        $query->bindValue(':limit', $limit, PDO::PARAM_INT);
        $query->bindValue(':offset', $offset, PDO::PARAM_INT);
        $query->execute();
        return $query->fetchAll();
    }

    public function countLegacyBlocks(?int $epoch): int
    {
        if ($epoch === null) {
            return (int) $this->pdo->query('SELECT COUNT(*) FROM blocks')->fetchColumn();
        }
        $query = $this->pdo->prepare(
            'SELECT COUNT(*) FROM blocks WHERE epoch_epoch_number = :epoch'
        );
        $query->execute(['epoch' => $epoch]);
        return (int) $query->fetchColumn();
    }

    public function legacyBonuses(
        ?int $epoch,
        string $search,
        int $limit,
        int $offset
    ): array {
        [$where, $parameters] = $this->bonusFilters($epoch, $search);
        $query = $this->pdo->prepare(
            'SELECT b.* FROM bonus b ' . $where
            . ' ORDER BY b.epoch_epoch_number DESC, b.amount DESC, '
            . 'b.delegator_stake_address ASC LIMIT :limit OFFSET :offset'
        );
        foreach ($parameters as $name => [$value, $type]) {
            $query->bindValue($name, $value, $type);
        }
        $query->bindValue(':limit', $limit, PDO::PARAM_INT);
        $query->bindValue(':offset', $offset, PDO::PARAM_INT);
        $query->execute();
        return $query->fetchAll();
    }

    public function countLegacyBonuses(?int $epoch, string $search): int
    {
        [$where, $parameters] = $this->bonusFilters($epoch, $search);
        $query = $this->pdo->prepare('SELECT COUNT(*) FROM bonus b ' . $where);
        foreach ($parameters as $name => [$value, $type]) {
            $query->bindValue($name, $value, $type);
        }
        $query->execute();
        return (int) $query->fetchColumn();
    }

    private function bonusFilters(?int $epoch, string $search): array
    {
        $clauses = [];
        $parameters = [];

        if ($epoch !== null) {
            $clauses[] = 'b.epoch_epoch_number = :epoch';
            $parameters[':epoch'] = [$epoch, PDO::PARAM_INT];
        }
        if ($search !== '') {
            $clauses[] = 'b.delegator_stake_address LIKE :search';
            $parameters[':search'] = ['%' . $search . '%', PDO::PARAM_STR];
        }

        return [
            $clauses === [] ? '' : 'WHERE ' . implode(' AND ', $clauses),
            $parameters,
        ];
    }
}
