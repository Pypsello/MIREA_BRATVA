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
    document.querySelectorAll('[data-open-modal]').forEach(card => {
        card.addEventListener('click', () => {
            const modal = document.getElementById(card.dataset.openModal);
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        });
    });

    document.querySelectorAll('[data-close-modal]').forEach(button => {
        button.addEventListener('click', () => {
            const modal = button.closest('.card-modal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        });
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            document.querySelectorAll('.card-modal.active').forEach(modal => {
                modal.classList.remove('active');
            });
            document.body.style.overflow = '';
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
    const revealedCard = document.getElementById('revealed-card');

    if (!revealButton || !openingStage || !revealStage) {
        return;
    }

    revealButton.addEventListener('click', () => {
        revealButton.classList.add('opening');
        openingStage.classList.add('stage-fade');

        setTimeout(() => {
            openingStage.classList.add('hidden');
            revealStage.classList.remove('hidden');
            requestAnimationFrame(() => {
                revealStage.classList.add('show');
                if (revealedCard) {
                    revealedCard.classList.add('revealed');
                }
            });
        }, 1150);
    });
}
