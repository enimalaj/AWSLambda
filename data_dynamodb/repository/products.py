from boto3.dynamodb.conditions import Key, Attr
from dynamodb_json import json_util

from data_common.constants import product_attributes, base_attributes
from data_common.exceptions import BadParameters, NoSuchEntity, CannotModifyEntityStates, MissingRequiredKey
from data_common.repository import ProductRepository
from data_common.notifications import SnsNotifier
from data_common.utils import clean
from data_dynamodb.utils import check_for_required_keys, check_properties_datatypes


class DynamoProductRepository(ProductRepository, SnsNotifier):
    def get_all_products(self, supplier):
        table = 'brewoptix-products'

        if isinstance(supplier, list):
            response_items = []
            for item in supplier:
                query = {
                    'KeyConditionExpression': Key('supplier_id').eq(item),
                    'FilterExpression':
                        (Attr('latest').eq(True) & Attr('active').eq(True)),
                    'IndexName': 'by_supplier_id'
                }
                response = self._storage.get_items(table, query)
                response_items.extend(response['Items'])
        else:
            query = {
                'KeyConditionExpression': Key('supplier_id').eq(supplier),
                'FilterExpression':
                    (Attr('latest').eq(True) & Attr('active').eq(True)),
                'IndexName': 'by_supplier_id'
            }
            response = self._storage.get_items(table, query)
            response_items = response['Items']

        products_obj = []

        for item in response_items:
            # The 4 lines below can be uncommented if we move
            # from ALL to KEYS_ONLY for the table
            # entity_id = item['EntityID']
            # product = self._storage.get(table, entity_id)
            # product = clean(product)
            product = json_util.loads(clean(item))
            products_obj.append(product)

        return products_obj

    def save_product(self, obj):
        table = 'brewoptix-products'

        check_for_required_keys(obj, product_attributes)
        content = {k: v for k, v in obj.items() if k not in base_attributes}
        check_properties_datatypes(content, product_attributes)

        obj['user_id'] = self._user_id

        product_type_obj = self._storage.save(table, obj)
        self.sns_publish("products", obj)  # publish notification

        product_type = clean(product_type_obj)

        return product_type

    def get_product_by_id(self, supplier_id, entity_id):
        table = 'brewoptix-products'

        product_type = self._storage.get(table, entity_id)
        if product_type:
            product_type = clean(product_type)

            if product_type["supplier_id"] != supplier_id:
                raise NoSuchEntity
        else:
            raise NoSuchEntity

        return product_type

    def delete_product_by_id(self, supplier_id, entity_id):
        table = 'brewoptix-products'

        product = self._storage.get(table, entity_id)

        if product:
            obj = clean(product)

            if product["supplier_id"] != supplier_id:
                raise NoSuchEntity

            obj["active"] = False
            self._storage.save(table, obj)
            self.sns_publish("products", obj)  # publish notification
        else:
            raise NoSuchEntity
