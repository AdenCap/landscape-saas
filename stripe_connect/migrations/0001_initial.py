# Generated migration for Stripe Connect models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('businesses', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConnectedAccountProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_product_id', models.CharField(db_index=True, help_text='Stripe Product ID (prod_...)', max_length=255, unique=True)),
                ('stripe_price_id', models.CharField(db_index=True, help_text='Stripe Price ID (price_...)', max_length=255)),
                ('name', models.CharField(help_text='Product name', max_length=255)),
                ('description', models.TextField(blank=True, help_text='Product description')),
                ('price_amount', models.DecimalField(decimal_places=2, help_text='Price in dollars (e.g. 29.99)', max_digits=10)),
                ('currency', models.CharField(default='usd', help_text='Currency code (e.g. usd)', max_length=3)),
                ('active', models.BooleanField(default=True, help_text='Whether the product is active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(help_text='The business (connected account) that owns this product', on_delete=django.db.models.deletion.CASCADE, related_name='stripe_products', to='businesses.business')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ConnectedAccountSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_subscription_id', models.CharField(db_index=True, help_text='Stripe Subscription ID (sub_...)', max_length=255, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('trialing', 'Trialing'), ('past_due', 'Past due'), ('canceled', 'Canceled'), ('unpaid', 'Unpaid')], help_text='Current subscription status', max_length=32)),
                ('current_period_end', models.DateTimeField(blank=True, help_text='When the current billing period ends', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(help_text='The connected account (business) with this subscription', on_delete=django.db.models.deletion.CASCADE, related_name='connect_subscriptions', to='businesses.business')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='connectedaccountproduct',
            index=models.Index(fields=['business', 'active'], name='stripe_conn_busines_idx'),
        ),
    ]
