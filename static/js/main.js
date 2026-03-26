function confirmAction(message) {
    return confirm(message);
}

function openCardPack() {
    const pack = document.querySelector('.card-pack');
    if (pack) {
        pack.classList.add('opening');
        setTimeout(() => pack.classList.remove('opening'), 1000);
    }
}

function filterCards() {
    const rarityFilter = document.getElementById('rarity-filter');
    const subjectFilter = document.getElementById('subject-filter');

    if (rarityFilter && subjectFilter) {
        const rarity = rarityFilter.value;
        const subject = subjectFilter.value;
        const cards = document.querySelectorAll('.card-item');

        cards.forEach(card => {
            let show = true;
            if (rarity && !card.classList.contains(`rarity-${rarity}`)) {
                show = false;
            }
            if (subject) {
                const cardSubject = card.querySelector('.card-subject')?.textContent;
                if (cardSubject !== subject) {
                    show = false;
                }
            }
            card.style.display = show ? 'block' : 'none';
        });
    }
}

function updateCoinBalance(newBalance) {
    const coinElement = document.querySelector('.coins');
    if (coinElement) {
        coinElement.textContent = `💰 ${newBalance}`;
    }
}

function initCardModals() {
    const modals = Array.from(document.querySelectorAll('.card-modal'));
    modals.forEach(modal => {
        if (!modal.classList.contains('portal-ready')) {
            document.body.appendChild(modal);
            modal.classList.add('portal-ready');
        }
    });

    const closeAllModals = () => {
        document.querySelectorAll('.card-modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
    };

    document.querySelectorAll('[data-open-modal]').forEach(card => {
        card.addEventListener('click', () => {
            const modal = document.getElementById(card.dataset.openModal);
            if (modal) {
                closeAllModals();
                modal.classList.add('active');
            }
        });
    });

    document.querySelectorAll('[data-close-modal]').forEach(button => {
        button.addEventListener('click', () => {
            const modal = button.closest('.card-modal');
            if (modal) {
                modal.classList.remove('active');
            }
        });
    });

    document.addEventListener('click', event => {
        const modal = event.target.closest('.card-modal.active');
        if (!modal) return;
        const content = event.target.closest('.card-modal-content');
        if (!content) {
            modal.classList.remove('active');
        }
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            closeAllModals();
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const rarityFilter = document.getElementById('rarity-filter');
    const subjectFilter = document.getElementById('subject-filter');

    if (rarityFilter) {
        rarityFilter.addEventListener('change', filterCards);
    }
    if (subjectFilter) {
        subjectFilter.addEventListener('change', filterCards);
    }

    initCardModals();
    initPackReveal();
});


function initPackReveal() {
    const revealButton = document.getElementById('reveal-pack-button');
    const openingStage = document.getElementById('pack-opening-stage');
    const revealStage = document.getElementById('pack-reveal-stage');
    const revealedCards = document.querySelectorAll('[data-revealed-card]');

    if (!revealButton || !openingStage || !revealStage) {
        return;
    }

    const packCount = Number(revealButton.dataset.packCount || openingStage.dataset.packCount || 1);

    revealButton.addEventListener('click', () => {
        if (revealButton.classList.contains('opening')) {
            return;
        }

        revealButton.classList.add('opening');
        openingStage.classList.add('stage-fade');

        if (packCount >= 3) {
            openingStage.classList.add('pack-stage-burst');
        }
        if (packCount >= 5) {
            openingStage.classList.add('pack-stage-overdrive');
        }

        let delay = 1150;
        let stagger = 140;

        if (packCount === 3) {
            delay = 1500;
            stagger = 170;
        } else if (packCount >= 5) {
            delay = 1850;
            stagger = 120;
        }

        setTimeout(() => {
            openingStage.classList.add('hidden');
            revealStage.classList.remove('hidden');
            requestAnimationFrame(() => revealStage.classList.add('show'));

            revealedCards.forEach((card, index) => {
                setTimeout(() => card.classList.add('revealed'), index * stagger);
            });
        }, delay);
    });
}
