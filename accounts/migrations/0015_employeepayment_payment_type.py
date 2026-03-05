from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_add_manager_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeepayment',
            name='payment_type',
            field=models.CharField(
                choices=[
                    ('regular', 'Regular Pay'),
                    ('bonus', 'Bonus'),
                    ('deduction', 'Deduction'),
                    ('reimbursement', 'Reimbursement'),
                ],
                default='regular',
                max_length=20,
            ),
        ),
    ]
